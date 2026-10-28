import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from ..config import Settings

LANG_TAGS = {"zh": "zh-CN", "en": "en-US", "ja": "ja-JP", "ko": "ko-KR"}


@dataclass
class Segment:
    start: float
    end: float
    text: str
    confidence: float | None = None


class AsrUnavailable(Exception):
    """转写引擎不可用（未安装或未启用），消息会展示给用户。"""


class AsrProvider(Protocol):
    def transcribe(self, path: Path, on_progress: Callable[[float], None]) -> tuple[str, list[Segment]]:
        """转写单声道音频，返回 (BCP 47 语种, 片段)；on_progress 参数为 0~1。"""


class FasterWhisperProvider:
    def __init__(self, settings: Settings):
        try:
            from faster_whisper import WhisperModel  # noqa: F401
        except ImportError:
            raise AsrUnavailable("未安装转写引擎：请执行 pip install -r requirements-asr.txt")
        self._settings = settings
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._model is None:
                from faster_whisper import WhisperModel
                s = self._settings
                self._model = WhisperModel(s.whisper_model, device=s.whisper_device,
                                           compute_type=s.whisper_compute_type)
            return self._model

    def transcribe(self, path, on_progress):
        model = self._load()
        gen, info = model.transcribe(str(path), vad_filter=True)
        segments = []
        for seg in gen:
            text = seg.text.strip()
            if text:
                # avg_logprob 为对数概率，指数化后近似 0~1 的置信度
                conf = round(min(1.0, max(0.0, 2.718281828 ** seg.avg_logprob)), 2)
                segments.append(Segment(round(seg.start, 3), round(seg.end, 3), text, conf))
            if info.duration:
                on_progress(min(1.0, seg.end / info.duration))
        return LANG_TAGS.get(info.language, info.language or ""), segments


def build_provider(settings: Settings) -> tuple[AsrProvider | None, str]:
    """返回 (provider, 不可用原因)。"""
    name = settings.asr_provider.lower()
    if name in ("", "none"):
        return None, "未配置转写引擎：请设置 ASR_PROVIDER=faster-whisper"
    if name == "faster-whisper":
        try:
            return FasterWhisperProvider(settings), ""
        except AsrUnavailable as e:
            return None, str(e)
    return None, f"不支持的转写引擎：{settings.asr_provider}"
