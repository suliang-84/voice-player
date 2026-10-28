import math
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
    """模型在后台线程预加载（首次使用需联网下载），转写前通过 wait_ready 等待。"""

    def __init__(self, settings: Settings):
        try:
            from faster_whisper import WhisperModel  # noqa: F401
        except ImportError:
            raise AsrUnavailable("未安装转写引擎：请执行 pip install -r requirements-asr.txt")
        self._settings = settings
        self._model = None
        self._state = "idle"  # idle | loading | ready | failed
        self._error = ""
        self._done = threading.Event()
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        return self._state

    @property
    def error(self) -> str:
        return self._error

    def start_preload(self) -> None:
        """幂等：加载中或已就绪时不做事；失败后再次调用会重新尝试加载。"""
        with self._lock:
            if self._state in ("loading", "ready"):
                return
            self._state, self._error = "loading", ""
            self._done.clear()
        threading.Thread(target=self._load, name="asr-preload", daemon=True).start()

    def _load(self) -> None:
        try:
            from faster_whisper import WhisperModel
            s = self._settings
            self._model = WhisperModel(s.whisper_model, device=s.whisper_device, compute_type=s.whisper_compute_type)
            self._state = "ready"
        except Exception as e:
            self._error = str(e) or e.__class__.__name__
            self._state = "failed"
        finally:
            self._done.set()

    def wait_ready(self, timeout: float) -> None:
        if self._state == "idle":
            self.start_preload()
        if not self._done.wait(timeout):
            raise AsrUnavailable("转写模型仍在加载（首次使用需下载模型），请稍后重试")
        if self._state != "ready":
            raise AsrUnavailable(f"转写模型加载失败：{self._error}")

    def transcribe(self, path, on_progress):
        self.wait_ready(self._settings.asr_load_timeout)
        gen, info = self._model.transcribe(str(path), vad_filter=True)
        segments = []
        for seg in gen:
            text = seg.text.strip()
            if text:
                # avg_logprob 为对数概率，指数化后近似 0~1 的置信度
                conf = round(min(1.0, max(0.0, math.exp(seg.avg_logprob))), 2)
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
