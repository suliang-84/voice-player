from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import select

from .. import deps
from ..auth import current_user
from ..envelope import ok
from ..errors import AppError
from ..models import Task, Transcript, Translation
from ..services.pipeline import _iso, scenes_or_default, speakers_or_default

router = APIRouter(prefix="/api/v1", dependencies=[Depends(current_user)])

TrackQuery = Annotated[Literal["A", "B", "both"], Query()]
LANG_RE = r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$"


def _require_audio(request: Request, audio_id: str) -> None:
    deps.storage_of(request).require(audio_id)


def _transcript_json(t: Transcript) -> dict:
    return {"id": t.id, "trackId": t.track_id, "startTime": t.start_time, "endTime": t.end_time,
            "text": t.text, "confidence": t.confidence}


def _translation_json(t: Translation) -> dict:
    return {"id": t.id, "transcriptId": t.transcript_id, "trackId": t.track_id, "startTime": t.start_time,
            "endTime": t.end_time, "text": t.text, "confidence": t.confidence}


@router.get("/audios/{audio_id}/transcripts")
def get_transcripts(request: Request, audio_id: str, track: TrackQuery = "both"):
    _require_audio(request, audio_id)
    deps.pipeline_of(request).ensure_transcription(audio_id)
    db = deps.db_of(request)
    with db.session() as s:
        task = s.get(Task, audio_id)
        if task.status == "processing":
            raise AppError(40002, "转写尚未完成，请稍候",
                           {"taskId": task.task_id, "status": "processing", "progress": task.progress})
        base = {"audioId": audio_id, "status": task.status, "language": task.language,
                "generatedAt": _iso(task.generated_at or task.updated_at)}
        if task.status == "failed":
            return ok({**base, "items": [], "error": task.error})
        q = select(Transcript).where(Transcript.audio_id == audio_id).order_by(Transcript.start_time, Transcript.track_id)
        if track != "both":
            q = q.where(Transcript.track_id == track)
        return ok({**base, "items": [_transcript_json(t) for t in s.scalars(q)]})


class TranscriptEdit(BaseModel):
    text: str
    startTime: float | None = None
    endTime: float | None = None

    @field_validator("text")
    @classmethod
    def _text(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text 不能为空")
        return v.strip()


@router.put("/transcripts/{transcript_id}/text")
def edit_transcript(request: Request, transcript_id: str, body: TranscriptEdit):
    with deps.db_of(request).session() as s:
        t = s.get(Transcript, transcript_id)
        if not t:
            raise AppError(404, "转写片段不存在")
        start = t.start_time if body.startTime is None else body.startTime
        end = t.end_time if body.endTime is None else body.endTime
        if start < 0 or end <= start:
            raise AppError(400, "endTime 必须大于 startTime")
        t.text, t.start_time, t.end_time = body.text, start, end
        s.commit()
        s.refresh(t)
        return ok({"id": t.id, "trackId": t.track_id, "text": t.text, "startTime": t.start_time,
                   "endTime": t.end_time, "updatedAt": _iso(t.updated_at)}, "转写内容更新成功")


@router.get("/audios/{audio_id}/translations")
def get_translations(request: Request, audio_id: str, track: TrackQuery = "both",
                     language: Annotated[str | None, Query(pattern=LANG_RE)] = None):
    _require_audio(request, audio_id)
    settings, pipeline, db = deps.settings_of(request), deps.pipeline_of(request), deps.db_of(request)
    language = language or settings.default_translation_language
    task = pipeline.ensure_transcription(audio_id)
    with db.session() as s:
        task = s.get(Task, audio_id)
        status = task.status
    base = {"audioId": audio_id, "status": status, "targetLanguage": language}
    if status != "completed":
        return ok({**base, "items": [], "generatedAt": _iso(task.updated_at)})

    def query():
        q = select(Translation).where(Translation.audio_id == audio_id, Translation.language == language)
        if track != "both":
            q = q.where(Translation.track_id == track)
        with db.session() as s:
            return list(s.scalars(q.order_by(Translation.start_time, Translation.track_id)))

    rows = query()
    if not rows:
        pipeline.translate_on_demand(audio_id, language)  # 未配置大模型时为空操作
        rows = query()
    gen = max((r.updated_at for r in rows), default=task.updated_at)
    return ok({**base, "items": [_translation_json(r) for r in rows], "generatedAt": _iso(gen)})


class TranslationEdit(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def _text(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text 不能为空")
        return v.strip()


@router.put("/translations/{translation_id}")
def edit_translation(request: Request, translation_id: str, body: TranslationEdit):
    with deps.db_of(request).session() as s:
        t = s.get(Translation, translation_id)
        if not t:
            raise AppError(404, "翻译片段不存在")
        t.text = body.text
        s.commit()
        s.refresh(t)
        return ok({"id": t.id, "transcriptId": t.transcript_id, "trackId": t.track_id, "text": t.text,
                   "updatedAt": _iso(t.updated_at)}, "翻译内容更新成功")


@router.get("/audios/{audio_id}/speakers")
def get_speakers(request: Request, audio_id: str):
    _require_audio(request, audio_id)
    deps.pipeline_of(request).ensure_transcription(audio_id)
    tracks = deps.storage_of(request).track_ids(audio_id)
    return ok({"audioId": audio_id, **speakers_or_default(deps.db_of(request), audio_id, tracks)})


@router.get("/audios/{audio_id}/scenes")
def get_scenes(request: Request, audio_id: str):
    _require_audio(request, audio_id)
    deps.pipeline_of(request).ensure_transcription(audio_id)
    return ok({"audioId": audio_id, **scenes_or_default(deps.db_of(request), audio_id)})
