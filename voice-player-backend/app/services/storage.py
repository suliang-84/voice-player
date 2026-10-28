import re
import shutil
import subprocess
from pathlib import Path

import soundfile as sf

from ..config import Settings
from ..errors import AppError, audio_not_found

AUDIO_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
ALLOWED_EXTS = {".wav", ".flac", ".ogg", ".oga", ".mp3", ".m4a", ".aac", ".opus", ".webm", ".wma"}
TRACKS = ("A", "B")


def validate_audio_id(audio_id: str) -> str:
    if not AUDIO_ID_RE.match(audio_id) or ".." in audio_id:
        raise AppError(400, "audioId 格式不正确")
    return audio_id


class Storage:
    """音频文件与派生缓存：data/audios/{audioId}.<ext>，data/cache/{audioId}/..."""

    def __init__(self, settings: Settings):
        self.settings = settings

    # ── 原始文件 ──────────────────────────────────────────────────────────
    def find(self, audio_id: str) -> Path | None:
        validate_audio_id(audio_id)
        for ext in ALLOWED_EXTS:
            p = self.settings.audio_dir / f"{audio_id}{ext}"
            if p.is_file():
                return p
        return None

    def require(self, audio_id: str) -> Path:
        p = self.find(audio_id)
        if p is None:
            raise audio_not_found(audio_id)
        return p

    def exists(self, audio_id: str) -> bool:
        return self.find(audio_id) is not None

    def target_path(self, audio_id: str, ext: str) -> Path:
        return self.settings.audio_dir / f"{audio_id}{ext}"

    def cache_dir(self, audio_id: str) -> Path:
        d = self.settings.cache_dir / audio_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def remove(self, audio_id: str) -> None:
        p = self.find(audio_id)
        if p:
            p.unlink(missing_ok=True)
        shutil.rmtree(self.settings.cache_dir / audio_id, ignore_errors=True)

    # ── 可读 WAV ──────────────────────────────────────────────────────────
    def source_wav(self, audio_id: str) -> Path:
        """返回 soundfile 可直接读取的文件；不可读时用 ffmpeg 转为 PCM WAV 并缓存。"""
        src = self.require(audio_id)
        if _readable(src):
            return src
        out = self.cache_dir(audio_id) / "source.wav"
        if not _fresh(out, src):
            self._transcode(src, out)
        return out

    def _transcode(self, src: Path, out: Path) -> None:
        tmp = out.with_suffix(".tmp.wav")
        cmd = [self.settings.ffmpeg_bin, "-nostdin", "-y", "-v", "error", "-i", str(src),
               "-vn", "-acodec", "pcm_s16le", str(tmp)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=self.settings.ffmpeg_timeout)
        except FileNotFoundError:
            raise AppError(50001, "该格式需要 ffmpeg 转码，但未找到 ffmpeg")
        except subprocess.TimeoutExpired:
            tmp.unlink(missing_ok=True)
            raise AppError(50002, "音频转码超时")
        if r.returncode != 0 or not tmp.exists():
            tmp.unlink(missing_ok=True)
            raise AppError(50002, f"音频转码失败：{r.stderr.strip()[-200:]}")
        tmp.replace(out)

    # ── 单声道 WAV（按轨道） ──────────────────────────────────────────────
    def channels(self, audio_id: str) -> int:
        return sf.info(self.source_wav(audio_id)).channels

    def track_ids(self, audio_id: str) -> list[str]:
        return list(TRACKS[: min(2, self.channels(audio_id))])

    def track_wav(self, audio_id: str, track: str) -> Path:
        from . import audio  # 避免循环导入
        src = self.source_wav(audio_id)
        ids = list(TRACKS[: min(2, sf.info(src).channels)])
        if track not in ids:
            raise AppError(400, f"该音频没有 {track} 轨（单声道音频只有 A 轨）")
        out = self.cache_dir(audio_id) / f"track_{track}.wav"
        if not _fresh(out, src):
            audio.extract_channel(src, TRACKS.index(track), out)
        return out


def _readable(path: Path) -> bool:
    try:
        sf.info(path)
        return True
    except Exception:
        return False


def _fresh(cache: Path, src: Path) -> bool:
    return cache.is_file() and cache.stat().st_mtime >= src.stat().st_mtime
