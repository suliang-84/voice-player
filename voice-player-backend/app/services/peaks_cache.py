"""峰值缓存：按 (audioId, maxLength) 存 JSON，源文件更新后自动失效。"""
import json
from datetime import datetime, timezone
from pathlib import Path

from ..config import Settings
from . import audio
from .storage import Storage


def get_peaks(settings: Settings, storage: Storage, audio_id: str, max_length: int) -> dict:
    src = storage.source_wav(audio_id)
    cache: Path = storage.cache_dir(audio_id) / f"peaks_{max_length}.json"
    if cache.is_file() and cache.stat().st_mtime >= src.stat().st_mtime:
        return json.loads(cache.read_text())
    info = audio.info(src)
    peaks = audio.compute_peaks(src, max_length)
    data = {"duration": info["duration"], "sampleRate": info["sampleRate"], "tracks": peaks,
            "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    tmp = cache.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    tmp.replace(cache)
    return data
