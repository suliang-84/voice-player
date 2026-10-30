from app.config import Settings
from app.main import build_llm
from app.services import audio
from app.services.asr import build_provider
from app.services.mock import LINES_A, LINES_B, MockAsrProvider, MockLlm, speech_spans
from conftest import make_mono, make_stereo, upload, wait_task
from test_audio import make_dialog

API = "/api/v1/audios"
EN = {en for en, _ in LINES_A + LINES_B}


def test_speech_spans_follow_real_activity(tmp_path):
    make_dialog(tmp_path / "d.wav")  # A 0~2s、B 5~7s 说话，8.0s 有 0.05s 的咳嗽
    rms, _, _ = audio.frame_rms(tmp_path / "d.wav", 10)
    # 整条双声道文件：直接按第一声道（A）检测
    spans = speech_spans(tmp_path / "d.wav")
    assert len(spans) == 1 and spans[0][0] < 0.2 and abs(spans[0][1] - 2.0) < 0.3  # 咳嗽太短，被丢弃
    assert all(e > s for s, e in spans) and all(spans[i][1] <= spans[i + 1][0] for i in range(len(spans) - 1))


def test_long_speech_is_split(tmp_path):
    make_stereo(tmp_path / "t.wav", seconds=30, silence=(100, 101))  # A 轨 30 秒连续有声
    spans = speech_spans(tmp_path / "t.wav")
    assert len(spans) >= 4 and all(e - s <= 9.0 for s, e in spans)
    assert abs(spans[0][0]) < 0.2 and abs(spans[-1][1] - 30) < 0.3


def test_mock_provider_is_deterministic_and_in_range(tmp_path):
    make_mono(tmp_path / "m.wav", seconds=6)
    p = MockAsrProvider(Settings(mock_delay=0))
    progress = []
    lang, segs = p.transcribe(tmp_path / "m.wav", progress.append)
    assert lang == "en-US" and progress[-1] == 1.0 and progress == sorted(progress)
    assert segs and all(0 <= s.start < s.end <= 6.01 and s.text in EN for s in segs)
    assert segs[0].text == LINES_A[0][0]  # 开场第一句固定
    _, again = p.transcribe(tmp_path / "m.wav", lambda _: None)
    assert [(s.start, s.end, s.text, s.confidence) for s in segs] == [(s.start, s.end, s.text, s.confidence) for s in again]


def test_mock_track_b_uses_designer_lines(tmp_path):
    make_mono(tmp_path / "track_B.wav", seconds=6)
    _, segs = MockAsrProvider(Settings(mock_delay=0)).transcribe(tmp_path / "track_B.wav", lambda _: None)
    assert segs[0].text == LINES_B[0][0] and all(s.text in {en for en, _ in LINES_B} for s in segs)


def test_config_selects_mock():
    assert isinstance(build_provider(Settings(asr_provider="mock"))[0], MockAsrProvider)
    assert isinstance(build_llm(Settings(llm_provider="mock")), MockLlm)
    assert build_llm(Settings()) is None  # 默认不启用大模型


def test_mock_end_to_end(make_client, tmp_path):
    c = make_client(asr=MockAsrProvider(Settings(mock_delay=0)), llm=MockLlm())
    upload(c, tmp_path, audio_id="a1", maker=make_dialog)
    wait_task(c, "a1")
    d = c.get(f"{API}/a1/transcripts").json()["data"]
    assert d["status"] == "completed" and d["language"] == "en-US"
    assert {i["trackId"] for i in d["items"]} == {"A", "B"}
    sp = {s["trackId"]: s for s in c.get(f"{API}/a1/speakers").json()["data"]["speakers"]}
    assert "项目经理" in sp["A"]["identity"] and sp["B"]["identity"] == "工业设计师"
    sc = c.get(f"{API}/a1/scenes").json()["data"]
    assert sc["scenes"][0]["type"] == "meeting" and sc["callPurpose"]
    # 中文译文来自内置对照；默认语种（en）与转写相同
    zh = c.get(f"{API}/a1/translations", params={"language": "zh"}).json()["data"]["items"]
    assert zh and all(any("一" <= ch <= "鿿" for ch in i["text"]) for i in zh)
    en = c.get(f"{API}/a1/translations").json()["data"]["items"]
    assert {i["text"] for i in en} <= EN


def test_mock_llm_translate_fallbacks():
    llm = MockLlm()
    out = llm.translate([{"id": "1", "text": "Right."}, {"id": "2", "text": "我改过的句子"}], "zh")
    assert out == {"1": "好的。", "2": "[zh] 我改过的句子"}
    assert llm.translate([{"id": "1", "text": "Right."}], "ja") == {"1": "[ja] Right."}
