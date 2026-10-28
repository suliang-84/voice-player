"""转写引擎加载：慢加载 / 加载失败时任务不卡死，引擎恢复后自动重试。"""
import threading
import time
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.services.asr import AsrUnavailable, FasterWhisperProvider
from conftest import FakeAsr, upload, wait_task

API = "/api/v1"


class FakeEngine(FakeAsr):
    """可控的引擎：模拟 faster-whisper provider 的 state / start_preload / wait_ready。"""

    def __init__(self):
        self.state, self.error = "loading", ""
        self.ready = threading.Event()
        self.preloads = 0

    def start_preload(self):
        if self.state in ("loading", "ready"):
            return
        self.preloads += 1  # 重新加载：本测试里网络仍不通，因此再次失败，保留错误原因

    def wait_ready(self, timeout):
        if not self.ready.wait(timeout):
            raise AsrUnavailable("转写模型仍在加载（首次使用需下载模型），请稍后重试")
        if self.state != "ready":
            raise AsrUnavailable(f"转写模型加载失败：{self.error}")

    def become_ready(self):
        self.state = "ready"
        self.ready.set()


def test_slow_load_fails_fast_then_retries_when_ready(make_client, tmp_path):
    eng = FakeEngine()
    c = make_client(asr=eng, asr_load_timeout=0.2)
    assert c.get("/health").json()["data"]["asrState"] == "loading"
    upload(c, tmp_path, audio_id="a1")

    d = wait_task(c, "a1").json()["data"]
    assert d["status"] == "failed" and d["error"].startswith("转写引擎不可用：") and "仍在加载" in d["error"]
    # 仍在加载时再次访问不会重启任务（避免反复等待）
    assert c.get(f"{API}/audios/a1/transcripts").json()["data"]["status"] == "failed"

    eng.become_ready()  # 模型下载完成
    d = wait_task(c, "a1").json()["data"]
    assert d["status"] == "completed" and len(d["items"]) == 2 and "error" not in d
    assert c.get("/health").json()["data"]["asr"] is True


def test_load_failure_reports_reason_and_retries_after_cooldown(make_client, tmp_path):
    eng = FakeEngine()
    c = make_client(asr=eng, asr_load_timeout=1, asr_retry_interval=0.6)
    eng.state, eng.error = "failed", "ConnectError: huggingface.co 不可达"  # 启动后的加载失败
    eng.ready.set()
    upload(c, tmp_path, audio_id="a1")
    d = wait_task(c, "a1").json()["data"]
    assert d["status"] == "failed" and "模型加载失败" in d["error"] and "huggingface.co" in d["error"]
    h = c.get("/health").json()["data"]
    assert h["asr"] is False and h["asrState"] == "failed" and "huggingface.co" in h["asrError"]

    # 冷却期内反复访问：保持失败，不重试（否则前端永远看不到失败）
    for _ in range(5):
        assert c.get(f"{API}/audios/a1/transcripts").json()["data"]["status"] == "failed"
    assert eng.preloads == 0

    # 冷却结束后再访问：重新尝试加载一次（本测试里仍失败）
    time.sleep(0.7)
    c.get(f"{API}/audios/a1/transcripts")
    assert eng.preloads == 1
    d = wait_task(c, "a1").json()["data"]
    assert d["status"] == "failed" and "huggingface.co" in d["error"]


def test_no_engine_is_not_retried(make_client, tmp_path):
    c = make_client(asr=None)
    upload(c, tmp_path, audio_id="a1")
    d = wait_task(c, "a1").json()["data"]
    assert d["status"] == "failed" and d["error"].startswith("转写引擎不可用：")
    h = c.get("/health").json()["data"]
    assert h["asrState"] == "unavailable" and h["status"] == "degraded"


# ── 真实 FasterWhisperProvider（打桩 WhisperModel，不联网） ─────────────────────
def patch_model(monkeypatch, factory):
    import faster_whisper
    monkeypatch.setattr(faster_whisper, "WhisperModel", factory)


def provider(**kw) -> FasterWhisperProvider:
    return FasterWhisperProvider(Settings(asr_load_timeout=2, **kw))


def test_provider_preload_ready_and_transcribe(monkeypatch, tmp_path):
    class Model:
        def __init__(self, name, device, compute_type):
            self.args = (name, device, compute_type)

        def transcribe(self, path, vad_filter):
            assert vad_filter is True
            segs = [SimpleNamespace(start=0.12349, end=2.5, text="  你好  ", avg_logprob=-0.1),
                    SimpleNamespace(start=3.0, end=4.0, text="   ", avg_logprob=-0.2),  # 空文本被丢弃
                    SimpleNamespace(start=5.0, end=10.0, text="再见", avg_logprob=-9.0)]
            return iter(segs), SimpleNamespace(duration=10.0, language="zh")

    patch_model(monkeypatch, Model)
    p = provider(whisper_model="base", whisper_device="cpu", whisper_compute_type="int8")
    assert p.state == "idle"
    p.start_preload()
    p.wait_ready(2)
    assert p.state == "ready" and p._model.args == ("base", "cpu", "int8")

    progress = []
    lang, segs = p.transcribe(tmp_path / "x.wav", progress.append)
    assert lang == "zh-CN"
    assert [(s.start, s.end, s.text) for s in segs] == [(0.123, 2.5, "你好"), (5.0, 10.0, "再见")]
    assert segs[0].confidence == 0.9 and 0 <= segs[1].confidence <= 0.01  # exp(-0.1)≈0.9，极低概率→接近 0
    assert progress[-1] == 1.0 and all(0 <= x <= 1 for x in progress)


def test_provider_load_failure_then_recover(monkeypatch):
    calls = {"n": 0}

    class Model:
        def __init__(self, *a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("网络不可达")

    patch_model(monkeypatch, Model)
    p = provider()
    p.start_preload()
    with pytest.raises(AsrUnavailable, match="模型加载失败：网络不可达"):
        p.wait_ready(2)
    assert p.state == "failed" and "网络不可达" in p.error
    p.start_preload()  # 失败后允许重新加载
    p.wait_ready(2)
    assert p.state == "ready" and calls["n"] == 2
    p.start_preload()  # 就绪后幂等
    assert calls["n"] == 2


def test_provider_wait_times_out_while_loading(monkeypatch):
    gate = threading.Event()

    class Model:
        def __init__(self, *a, **k):
            gate.wait(5)

    patch_model(monkeypatch, Model)
    p = provider()
    t0 = time.time()
    with pytest.raises(AsrUnavailable, match="仍在加载"):
        p.start_preload()
        p.wait_ready(0.2)
    assert time.time() - t0 < 2 and p.state == "loading"
    gate.set()
    p.wait_ready(2)
    assert p.state == "ready"
