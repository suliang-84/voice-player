"""静音检测缓存：按检测参数存 JSON，源文件更新后自动失效。"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from ..config import Settings
from . import audio
from .storage import Storage

ALGORITHM_VERSION = 3  # 检测算法变化时递增，让旧缓存失效


def get_silences(settings: Settings, storage: Storage, audio_id: str,
                 threshold: float | None, min_duration: float, speech_offset_db: float) -> dict:
    src = storage.source_wav(audio_id)
    params = dict(threshold=threshold, min_duration=min_duration, frame_ms=settings.silence_frame_ms,
                  min_speech=settings.silence_min_speech, padding=settings.silence_padding,
                  margin_db=settings.silence_margin_db, speech_offset_db=speech_offset_db,
                  smooth_ms=settings.silence_smooth_ms)

    def build(tmp: Path) -> None:
        result = audio.detect_silences(src, **params)
        result["generatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        tmp.write_text(json.dumps(result))

    key = hashlib.md5(json.dumps([ALGORITHM_VERSION, params], sort_keys=True).encode()).hexdigest()[:12]
    cache = storage.build_cached(storage.cache_dir(audio_id) / f"silences_{key}.json", src, build)
    return json.loads(cache.read_text())
