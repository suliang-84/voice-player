"""峰值缓存：按 (audioId, maxLength) 存 JSON，源文件更新后自动失效。"""
import json
from datetime import datetime, timezone
from pathlib import Path

from ..config import Settings
from . import audio
from .storage import Storage


def get_peaks(settings: Settings, storage: Storage, audio_id: str, max_length: int) -> dict:
    src = storage.source_wav(audio_id)

    def build(tmp: Path) -> None:
        info = audio.info(src)
        tmp.write_text(json.dumps({
            "duration": info["duration"], "sampleRate": info["sampleRate"],
            "tracks": audio.compute_peaks(src, max_length),
            "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }))

    cache = storage.build_cached(storage.cache_dir(audio_id) / f"peaks_{max_length}.json", src, build)
    return json.loads(cache.read_text())
