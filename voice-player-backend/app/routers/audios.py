import shutil
import uuid
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from .. import deps
from ..auth import current_user
from ..envelope import ok
from ..errors import AppError
from ..services import audio
from ..services.peaks_cache import get_peaks
from ..services.storage import ALLOWED_EXTS, validate_audio_id

router = APIRouter(prefix="/api/v1", dependencies=[Depends(current_user)])

TrackQuery = Annotated[Literal["A", "B", "both"], Query()]


def select_tracks(available: list[str], track: str) -> list[str]:
    if track == "both":
        return available
    if track not in available:
        raise AppError(400, f"该音频没有 {track} 轨（单声道音频只有 A 轨）")
    return [track]


@router.post("/audios")
async def upload_audio(request: Request, file: UploadFile = File(...), audioId: str | None = Form(None)):
    """上传音频并触发后台处理（峰值、转写）。契约之外的辅助接口。"""
    settings, storage, pipeline = deps.settings_of(request), deps.storage_of(request), deps.pipeline_of(request)
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

    try:
        info = await run_in_threadpool(lambda: audio.info(storage.source_wav(audio_id)))
    except AppError:
        storage.remove(audio_id)
        raise
    except Exception:
        storage.remove(audio_id)
        raise AppError(40003, "无法解析音频文件，格式不支持或文件已损坏")
    pipeline.on_uploaded(audio_id)
    return ok({"audioId": audio_id, **{k: info[k] for k in ("duration", "sampleRate", "channels")}})


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
def silences(request: Request, audio_id: str, track: TrackQuery = "both",
             threshold: Annotated[float | None, Query(ge=0, le=1)] = None,
             minDuration: Annotated[float | None, Query(ge=0)] = None):
    from datetime import datetime, timezone
    settings, storage = deps.settings_of(request), deps.storage_of(request)
    src = storage.source_wav(audio_id)
    result = audio.detect_silences(
        src,
        settings.default_silence_threshold if threshold is None else threshold,
        settings.default_silence_min_duration if minDuration is None else minDuration,
        settings.silence_frame_ms,
    )
    tracks = {tid: result[tid] for tid in select_tracks(list(result), track)}
    return ok({"tracks": tracks, "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
