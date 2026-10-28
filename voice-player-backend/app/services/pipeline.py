"""音频后台流水线：峰值预计算 → 逐声道转写 → 大模型分析/默认语种翻译。"""
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from sqlalchemy import delete, select

from ..config import Settings
from ..db import Database
from ..models import Analysis, Task, Transcript, Translation
from . import audio
from .asr import AsrProvider, AsrUnavailable
from .hub import Hub
from .llm import LlmClient, LlmError, default_scenes, unknown_speakers
from .storage import Storage

log = logging.getLogger("voice_player")

# 因转写引擎不可用而失败的任务带此前缀；引擎恢复后下次访问会自动重试
ENGINE_ERR = "转写引擎不可用："


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def fmt_ts(sec: float) -> str:
    return f"{int(sec // 60):02d}:{int(sec % 60):02d}"


class Pipeline:
    def __init__(self, settings: Settings, db: Database, storage: Storage, hub: Hub,
                 asr: AsrProvider | None, asr_error: str, llm: LlmClient | None):
        self.settings, self.db, self.storage, self.hub = settings, db, storage, hub
        self.asr, self.asr_error, self.llm = asr, asr_error, llm
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pipeline")
        self._inflight: set[str] = set()
        self._engine_failed_at = 0.0

    # ── 入口 ──────────────────────────────────────────────────────────────
    def on_uploaded(self, audio_id: str) -> None:
        self._pool.submit(self._precompute_peaks, audio_id)
        self.ensure_transcription(audio_id)

    def engine_state(self) -> str:
        """ready | loading | failed | unavailable（未安装或未配置，需重启）。"""
        if self.asr is None:
            return "unavailable"
        return getattr(self.asr, "state", "ready")

    def _engine_retry_due(self) -> bool:
        state = self.engine_state()
        if state == "ready":
            return True
        # 加载失败：冷却期内保持失败，避免每次访问都重试导致前端永远看不到失败
        return state == "failed" and time.monotonic() - self._engine_failed_at >= self.settings.asr_retry_interval

    def ensure_transcription(self, audio_id: str) -> Task:
        """首次访问时创建并启动转写任务；因引擎不可用而失败的任务，在引擎恢复后重试。"""
        with self.db.session() as s:
            task = s.get(Task, audio_id)
            if task:
                if not (task.status == "failed" and task.error.startswith(ENGINE_ERR) and self._engine_retry_due()):
                    return task
                if self.engine_state() == "failed":
                    self.asr.start_preload()  # 重新尝试加载模型
                task.status, task.progress, task.error = "processing", 0, ""
            else:
                task = Task(audio_id=audio_id, task_id=new_id("task_transcribe"), status="processing", progress=0)
                s.add(task)
            s.commit()
        self._submit(audio_id)
        return task

    def resume_unfinished(self) -> None:
        with self.db.session() as s:
            ids = list(s.scalars(select(Task.audio_id).where(Task.status == "processing")))
        for audio_id in ids:
            self._submit(audio_id)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    def _submit(self, audio_id: str) -> None:
        if audio_id in self._inflight:
            return
        self._inflight.add(audio_id)
        self._pool.submit(self._run_guarded, audio_id)

    # ── 峰值 ──────────────────────────────────────────────────────────────
    def _precompute_peaks(self, audio_id: str) -> None:
        from .peaks_cache import get_peaks
        try:
            get_peaks(self.settings, self.storage, audio_id, self.settings.default_peaks_points)
            self.hub.publish({"type": "peaks_generated", "taskId": new_id("task_peak"),
                              "audioId": audio_id, "status": "completed"})
        except Exception:
            log.exception("peaks precompute failed: %s", audio_id)

    # ── 转写流水线 ────────────────────────────────────────────────────────
    def _run_guarded(self, audio_id: str) -> None:
        try:
            self._run(audio_id)
        except Exception as e:
            log.exception("pipeline failed: %s", audio_id)
            self._fail(audio_id, str(e) or e.__class__.__name__)
        finally:
            self._inflight.discard(audio_id)

    def _task(self, s, audio_id: str) -> Task:
        return s.get(Task, audio_id)

    def _progress(self, audio_id: str, progress: int) -> None:
        with self.db.session() as s:
            t = self._task(s, audio_id)
            if progress <= t.progress:
                return
            t.progress = progress
            task_id = t.task_id
            s.commit()
        self.hub.publish({"type": "transcription_progress", "taskId": task_id, "audioId": audio_id,
                          "progress": progress, "status": "processing"})

    def _fail(self, audio_id: str, error: str) -> None:
        with self.db.session() as s:
            t = self._task(s, audio_id)
            t.status, t.error = "failed", error
            task_id, progress = t.task_id, t.progress
            s.commit()
        self.hub.publish({"type": "transcription_progress", "taskId": task_id, "audioId": audio_id,
                          "progress": progress, "status": "failed"})

    def _run(self, audio_id: str) -> None:
        if self.asr is None:
            return self._fail(audio_id, ENGINE_ERR + (self.asr_error or "未配置转写引擎"))
        wait_ready = getattr(self.asr, "wait_ready", None)
        if wait_ready:
            try:
                wait_ready(self.settings.asr_load_timeout)
            except AsrUnavailable as e:
                self._engine_failed_at = time.monotonic()
                return self._fail(audio_id, ENGINE_ERR + str(e))
        tracks = self.storage.track_ids(audio_id)
        src = self.storage.source_wav(audio_id)

        segments: list[tuple[str, object]] = []
        languages: dict[str, float] = {}
        for i, tid in enumerate(tracks):
            path = src if len(tracks) == 1 else self.storage.track_wav(audio_id, tid)
            base = i / len(tracks)

            def on_progress(frac: float, base=base):
                self._progress(audio_id, int((base + frac / len(tracks)) * 85))

            lang, segs = self.asr.transcribe(path, on_progress)
            segments += [(tid, sg) for sg in segs]
            if lang:
                languages[lang] = languages.get(lang, 0) + sum(sg.end - sg.start for sg in segs)
        segments.sort(key=lambda x: (x[1].start, x[0]))
        language = max(languages, key=languages.get) if languages else ""

        rows = [Transcript(id=new_id("transcript"), audio_id=audio_id, track_id=tid, start_time=sg.start,
                           end_time=max(sg.end, sg.start + 0.001), text=sg.text, confidence=sg.confidence)
                for tid, sg in segments]
        with self.db.session() as s:
            s.execute(delete(Transcript).where(Transcript.audio_id == audio_id))
            s.add_all(rows)
            s.commit()
        self._progress(audio_id, 90)

        if self.llm and rows:
            self._analyze(audio_id, tracks, rows)
            self._translate(audio_id, self.settings.default_translation_language)

        with self.db.session() as s:
            t = self._task(s, audio_id)
            t.status, t.progress, t.language, t.error = "completed", 100, language, ""
            t.generated_at = datetime.now(timezone.utc)
            task_id = t.task_id
            s.commit()
        self.hub.publish({"type": "transcription_completed", "taskId": task_id, "audioId": audio_id,
                          "status": "completed", "transcriptCount": len(rows)})

    # ── 大模型阶段（失败不影响转写结果） ───────────────────────────────────
    def _analyze(self, audio_id: str, tracks: list[str], rows: list[Transcript]) -> None:
        dialogue = "\n".join(f"[{r.track_id} {fmt_ts(r.start_time)}] {r.text}" for r in rows)
        try:
            result = self.llm.analyze(dialogue, tracks)
        except LlmError as e:
            log.warning("llm analyze failed for %s: %s", audio_id, e)
            return
        with self.db.session() as s:
            for kind, data in (("speakers", {"speakers": result["speakers"]}), ("scenes", result["scenes"])):
                s.merge(Analysis(audio_id=audio_id, kind=kind, data=data, generated_at=datetime.now(timezone.utc)))
            s.commit()

    def _translate(self, audio_id: str, language: str) -> None:
        with self.db.session() as s:
            rows = list(s.scalars(select(Transcript).where(Transcript.audio_id == audio_id)
                                  .order_by(Transcript.start_time)))
            done = {t.transcript_id for t in s.scalars(select(Translation).where(
                Translation.audio_id == audio_id, Translation.language == language))}
            todo = [r for r in rows if r.id not in done]
            if not todo:
                return
            try:
                result = self.llm.translate([{"id": r.id, "text": r.text} for r in todo], language)
            except LlmError as e:
                log.warning("llm translate failed for %s: %s", audio_id, e)
                return
            for r in todo:
                if r.id in result:
                    s.add(Translation(id=new_id("translation"), audio_id=audio_id, transcript_id=r.id,
                                      language=language, track_id=r.track_id, start_time=r.start_time,
                                      end_time=r.end_time, text=result[r.id]))
            s.commit()

    def translate_on_demand(self, audio_id: str, language: str) -> None:
        """接口里按需翻译其它语种（同步）；未配置大模型时什么也不做。"""
        if self.llm:
            self._translate(audio_id, language)


def speakers_or_default(db: Database, audio_id: str, track_ids: list[str]) -> dict:
    with db.session() as s:
        row = s.get(Analysis, (audio_id, "speakers"))
    if row:
        return {"speakers": row.data["speakers"], "generatedAt": _iso(row.generated_at)}
    return {"speakers": unknown_speakers(track_ids), "generatedAt": _iso(datetime.now(timezone.utc))}


def scenes_or_default(db: Database, audio_id: str) -> dict:
    with db.session() as s:
        row = s.get(Analysis, (audio_id, "scenes"))
    if row:
        return {**row.data, "generatedAt": _iso(row.generated_at)}
    return {**default_scenes(), "generatedAt": _iso(datetime.now(timezone.utc))}


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
