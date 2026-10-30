import shutil
import uuid
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

from .. import deps
from ..auth import current_user
from ..envelope import ok
from ..errors import AppError
from ..services import audio, ingest
from ..services.peaks_cache import get_peaks
from ..services.silence_cache import get_silences
from ..services.storage import ALLOWED_EXTS, validate_audio_id

router = APIRouter(prefix="/api/v1", dependencies=[Depends(current_user)])

TrackQuery = Annotated[Literal["A", "B", "both"], Query()]


def select_tracks(available: list[str], track: str) -> list[str]:
    if track == "both":
        return available
    if track not in available:
        raise AppError(400, f"该音频没有 {track} 轨（单声道音频只有 A 轨）")
    return [track]


async def _register(request: Request, audio_id: str) -> dict:
    """文件已落盘：解析音频信息，失败则清掉；成功则启动后台处理（峰值、转写）。上传与入库共用。"""
    storage, pipeline = deps.storage_of(request), deps.pipeline_of(request)
    try:
        info = await run_in_threadpool(lambda: audio.info(storage.source_wav(audio_id)))
    except AppError:
        storage.remove(audio_id)
        raise
    except Exception:
        storage.remove(audio_id)
        raise AppError(40003, "无法解析音频文件，格式不支持或文件已损坏")
    pipeline.on_uploaded(audio_id)
    return {"audioId": audio_id, **{k: info[k] for k in ("duration", "sampleRate", "channels")}}


@router.post("/audios")
async def upload_audio(request: Request, file: UploadFile = File(...), audioId: str | None = Form(None)):
    """上传音频并触发后台处理（峰值、转写）。契约之外的辅助接口，仅用于开发测试；生产环境用 /ingest。"""
    settings, storage = deps.settings_of(request), deps.storage_of(request)
    if not settings.upload_enabled:
        raise AppError(403, "上传接口已关闭，请通过 /audios/{audioId}/ingest 提交音频")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise AppError(40003, f"文件格式不支持：{ext or '无后缀'}")
    audio_id = validate_audio_id(audioId) if audioId else f"audio_{uuid.uuid4().hex[:10]}"
    if storage.exists(audio_id):
        raise AppError(400, f"audioId 已存在：{audio_id}")

    settings.ensure_dirs()
    target = storage.target_path(audio_id, ext)
    tmp = target.with_name(target.name + ".part")
    size = 0
    try:
        with tmp.open("wb") as out:
            while chunk := await file.read(1 << 20):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise AppError(40004, "文件大小超过限制")
                out.write(chunk)
        if size == 0:
            raise AppError(400, "文件为空")
        tmp.replace(target)
    finally:
        tmp.unlink(missing_ok=True)

    return ok(await _register(request, audio_id))


class IngestSource(BaseModel):
    type: Literal["url"]
    url: str
    headers: dict[str, str] | None = None  # 下载时附带的请求头，如对象存储或内部下载接口的鉴权
    ext: str | None = None  # 音频格式（如 wav、mp3）；地址没有后缀、对方也没给 Content-Type 时使用


class IngestBody(BaseModel):
    source: IngestSource
    force: bool = False  # 已入库时：false 直接返回已入库；true 删除旧数据并以新文件为准重新处理


_ingesting: set[str] = set()  # 正在入库的 audioId，防止同一个音频并发入库


@router.post("/audios/{audio_id}/ingest")
async def ingest_audio(request: Request, audio_id: str, body: IngestBody):
    """入库完成后由入库系统调用：按地址把音频拉到本地，并触发后台处理（峰值、转写）。
    音频不存在于本地时才下载；幂等，重复调用返回 alreadyIngested。契约之外的辅助接口。"""
    validate_audio_id(audio_id)
    settings, storage, pipeline = deps.settings_of(request), deps.storage_of(request), deps.pipeline_of(request)
    src = body.source
    ingest.check_url(settings, src.url)
    if audio_id in _ingesting:
        raise AppError(409, f"该音频正在入库：{audio_id}", http_status=409)
    _ingesting.add(audio_id)
    try:
        exists = storage.exists(audio_id)
        if exists and not body.force:
            info = await run_in_threadpool(lambda: audio.info(storage.source_wav(audio_id)))
            pipeline.ensure_transcription(audio_id)  # 上次入库中途失败时，重复调用能补上
            return ok({"audioId": audio_id, **{k: info[k] for k in ("duration", "sampleRate", "channels")},
                       "alreadyIngested": True}, "音频已入库")

        settings.ensure_dirs()
        tmp = settings.audio_dir / f"{audio_id}.ingest.part"
        try:
            # 先下载成功，再清旧数据：下载失败不会丢掉已有的音频和转写
            ext = await run_in_threadpool(ingest.download, settings, src.url, src.headers, src.ext, tmp)
            if exists:
                pipeline.reset(audio_id)
                storage.remove(audio_id)
            tmp.replace(storage.target_path(audio_id, ext))
        finally:
            tmp.unlink(missing_ok=True)

        return ok({**await _register(request, audio_id), "alreadyIngested": False}, "音频入库成功")
    finally:
        _ingesting.discard(audio_id)


@router.get("/audios/{audio_id}/stream")
async def stream(request: Request, audio_id: str, track: Annotated[Literal["A", "B"], Query()] = "A"):
    """返回指定轨道的单声道 WAV；FileResponse 负责 Range。"""
    storage = deps.storage_of(request)
    storage.require(audio_id)
    path = await run_in_threadpool(storage.track_wav, audio_id, track)
    return FileResponse(path, media_type="audio/wav", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/audios/{audio_id}/peaks")
def peaks(request: Request, audio_id: str, track: TrackQuery = "both",
          maxLength: Annotated[int | None, Query(ge=1, le=200000)] = None,
          precision: Annotated[int, Query(ge=0, le=6)] = 2):
    settings, storage = deps.settings_of(request), deps.storage_of(request)
    storage.require(audio_id)
    data = get_peaks(settings, storage, audio_id, maxLength or settings.default_peaks_points)
    tracks = {}
    for tid in select_tracks(list(data["tracks"]), track):
        pts = [round(v, precision) for v in data["tracks"][tid]]
        tracks[tid] = {"peaks": [pts], "duration": data["duration"], "pointCount": len(pts)}
    return ok({"duration": data["duration"], "sampleRate": data["sampleRate"], "tracks": tracks,
               "generatedAt": data["generatedAt"]})


@router.get("/audios/{audio_id}/silences")
async def silences(request: Request, audio_id: str, track: TrackQuery = "both",
                   threshold: Annotated[float | None, Query(ge=0, le=1)] = None,
                   minDuration: Annotated[float | None, Query(ge=0)] = None,
                   speechOffsetDb: Annotated[float | None, Query(ge=0, le=60)] = None):
    settings, storage = deps.settings_of(request), deps.storage_of(request)
    result = await run_in_threadpool(
        get_silences, settings, storage, audio_id,
        settings.default_silence_threshold if threshold is None else threshold,
        settings.default_silence_min_duration if minDuration is None else minDuration,
        settings.silence_speech_offset_db if speechOffsetDb is None else speechOffsetDb,
    )
    tracks = {tid: result["tracks"][tid] for tid in select_tracks(list(result["tracks"]), track)}
    data = {"tracks": tracks, "generatedAt": result["generatedAt"]}
    if track == "both":
        data["both"] = result["both"]
    return ok(data)


@router.get("/audios/{audio_id}/download")
async def download(request: Request, audio_id: str,
                   track: Annotated[Literal["A", "B", "mix", "stereo"], Query()] = "A",
                   start: Annotated[float | None, Query(ge=0)] = None,
                   end: Annotated[float | None, Query(gt=0)] = None):
    """下载音频文件（WAV）。track：A / B 单路，mix 两路混成单声道，stereo 立体声（A 左 B 右）；
    start / end 给出时只含该时间范围。契约之外的辅助接口。"""
    storage = deps.storage_of(request)
    storage.require(audio_id)
    src = await run_in_threadpool(storage.source_wav, audio_id)
    info = await run_in_threadpool(audio.info, src)
    if track == "B" and info["channels"] < 2:
        raise AppError(400, "该音频没有 B 轨（单声道音频只有 A 轨）")
    if start is not None and end is not None and end <= start:
        raise AppError(400, "end 必须大于 start")
    if start is not None and start >= info["duration"]:
        raise AppError(400, "start 超出音频时长")

    name = f"{audio_id}_{track}"
    if start is not None or end is not None:
        name += f"_{start or 0:.1f}-{min(end if end is not None else info['duration'], info['duration']):.1f}s"
    media = {"media_type": "audio/wav", "filename": f"{name}.wav"}

    if track in ("A", "B") and start is None and end is None:  # 整条单路：直接用声道缓存
        path = await run_in_threadpool(storage.track_wav, audio_id, track)
        return FileResponse(path, **media)

    tmp = storage.cache_dir(audio_id) / f"download_{uuid.uuid4().hex[:8]}.wav"
    try:
        await run_in_threadpool(audio.render_wav, src, tmp, track, start, end)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    return FileResponse(tmp, background=BackgroundTask(tmp.unlink, missing_ok=True), **media)
