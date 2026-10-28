import time

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.asr import Segment

SR = 16000


class FakeAsr:
    """每个声道返回固定片段：A 轨 0.5~3s，B 轨 4~6s。"""
    def transcribe(self, path, on_progress):
        on_progress(0.5)
        on_progress(1.0)
        info = sf.info(path)
        assert info.channels == 1
        if "track_A" in str(path):
            return "zh-CN", [Segment(0.5, 3.0, "您好，我是某运营商客服。", 0.9)]
        if "track_B" in str(path):
            return "zh-CN", [Segment(4.0, 6.0, "我的网络断了。", 0.8)]
        return "zh-CN", [Segment(0.5, 3.0, "单声道内容", 0.9)]


class FakeLlm:
    def __init__(self):
        self.translate_calls = 0

    def analyze(self, dialogue, track_ids):
        from app.services.llm import normalize_analysis
        return normalize_analysis({
            "speakers": [{"trackId": "A", "identity": "运营商客服人员", "confidence": 0.8, "role": "agent",
                          "emotionDistribution": {"neutral": 1}, "sentimentScore": 0.1, "dominantIntent": "support"},
                         {"trackId": "B", "identity": "客户", "confidence": 0.7, "role": "customer"}],
            "scenes": [{"type": "call_center", "subType": "technical_support", "confidence": 0.9,
                        "description": "技术支持通话", "keywords": ["网络"]}],
            "callType": "inbound", "callResolution": "resolved",
            "analysis": {"hasComplaint": True, "complaintScore": 0.5},
        }, track_ids)

    def translate(self, items, language, batch=40):
        self.translate_calls += 1
        return {it["id"]: f"[{language}] {it['text']}" for it in items}


def make_stereo(path, seconds=8, silence=(2.0, 4.0)):
    """A 轨：440Hz 正弦，silence 区间静音；B 轨：880Hz 正弦，全程有声。"""
    t = np.arange(int(SR * seconds)) / SR
    a = 0.5 * np.sin(2 * np.pi * 440 * t)
    a[(t >= silence[0]) & (t < silence[1])] = 0
    b = 0.3 * np.sin(2 * np.pi * 880 * t)
    sf.write(path, np.stack([a, b], axis=1).astype("float32"), SR, subtype="PCM_16")


def make_mono(path, seconds=3):
    t = np.arange(int(SR * seconds)) / SR
    sf.write(path, (0.5 * np.sin(2 * np.pi * 440 * t)).astype("float32"), SR, subtype="PCM_16")


@pytest.fixture
def make_client(tmp_path):
    clients = []

    def _make(*, asr="fake", llm=None, **overrides):
        settings = Settings(data_dir=tmp_path / "data", **overrides)
        app = create_app(settings, asr=FakeAsr() if asr == "fake" else None,
                         asr_error="未安装转写引擎" if asr != "fake" else "", llm=llm)
        c = TestClient(app)
        c.__enter__()
        clients.append(c)
        return c

    yield _make
    for c in clients:
        c.__exit__(None, None, None)


@pytest.fixture
def client(make_client):
    return make_client()


def upload(client, tmp_path, name="call.wav", audio_id=None, maker=make_stereo):
    p = tmp_path / name
    maker(p)
    with p.open("rb") as f:
        r = client.post("/api/v1/audios", files={"file": (name, f, "audio/wav")},
                        data={"audioId": audio_id} if audio_id else {})
    return r


def wait_task(client, audio_id, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/v1/audios/{audio_id}/transcripts")
        if r.json()["code"] != 40002:
            return r
        time.sleep(0.05)
    raise AssertionError("转写任务超时")
