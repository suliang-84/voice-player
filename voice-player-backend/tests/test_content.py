import time

from conftest import FakeLlm, make_mono, upload, wait_task

API = "/api/v1"


def test_transcripts_lazy_start_then_complete(client, tmp_path):
    # 不经上传、只放文件：首次 GET 也会启动任务
    upload(client, tmp_path, audio_id="a1")
    r = wait_task(client, "a1")
    d = r.json()["data"]
    assert d["status"] == "completed" and d["language"] == "zh-CN" and d["audioId"] == "a1"
    items = d["items"]
    assert [(i["trackId"], i["startTime"], i["endTime"]) for i in items] == [("A", 0.5, 3.0), ("B", 4.0, 6.0)]
    assert items[0]["text"] == "您好，我是某运营商客服。" and items[0]["confidence"] == 0.9
    assert all(i["id"] for i in items)


def test_transcripts_track_filter(client, tmp_path):
    upload(client, tmp_path, audio_id="a1")
    wait_task(client, "a1")
    only_b = client.get(f"{API}/audios/a1/transcripts", params={"track": "B"}).json()["data"]["items"]
    assert [i["trackId"] for i in only_b] == ["B"]


def test_40002_while_processing(make_client, tmp_path):
    import threading
    from conftest import FakeAsr
    gate = threading.Event()

    class Slow(FakeAsr):
        def transcribe(self, path, on_progress):
            gate.wait(5)
            return super().transcribe(path, on_progress)

    from fastapi.testclient import TestClient
    from app.config import Settings
    from app.main import create_app
    app = create_app(Settings(data_dir=tmp_path / "d"), asr=Slow())
    with TestClient(app) as c:
        upload(c, tmp_path, audio_id="a1")
        r = c.get(f"{API}/audios/a1/transcripts")
        body = r.json()
        assert r.status_code == 200 and body["code"] == 40002
        assert body["data"]["status"] == "processing" and body["data"]["taskId"].startswith("task_transcribe_")
        gate.set()
        assert wait_task(c, "a1").json()["data"]["status"] == "completed"


def test_failed_without_asr(make_client, tmp_path):
    c = make_client(asr=None)
    upload(c, tmp_path, audio_id="a1")
    d = wait_task(c, "a1").json()["data"]
    assert d["status"] == "failed" and "转写引擎" in d["error"] and d["items"] == []
    # 失败后再次访问不会无限重启任务
    assert c.get(f"{API}/audios/a1/transcripts").json()["data"]["status"] == "failed"


def test_edit_transcript_persists(client, tmp_path):
    upload(client, tmp_path, audio_id="a1")
    item = wait_task(client, "a1").json()["data"]["items"][0]
    r = client.put(f"{API}/transcripts/{item['id']}/text", json={"text": "  改后文本  ", "startTime": 1.0, "endTime": 2.5})
    d = r.json()
    assert d["message"] == "转写内容更新成功"
    assert d["data"]["text"] == "改后文本" and d["data"]["startTime"] == 1.0 and d["data"]["endTime"] == 2.5
    assert d["data"]["updatedAt"].endswith("Z")
    again = client.get(f"{API}/audios/a1/transcripts").json()["data"]["items"]
    assert any(i["id"] == item["id"] and i["text"] == "改后文本" for i in again)
    # 只改文本：时间保持
    r2 = client.put(f"{API}/transcripts/{item['id']}/text", json={"text": "再改"}).json()["data"]
    assert (r2["startTime"], r2["endTime"]) == (1.0, 2.5)


def test_edit_transcript_validation(client, tmp_path):
    upload(client, tmp_path, audio_id="a1")
    item = wait_task(client, "a1").json()["data"]["items"][0]
    url = f"{API}/transcripts/{item['id']}/text"
    assert client.put(url, json={"text": "  "}).status_code == 400
    assert client.put(url, json={}).status_code == 400
    assert client.put(url, json={"text": "x", "startTime": 5, "endTime": 5}).status_code == 400
    assert client.put(url, json={"text": "x", "endTime": 0.1}).status_code == 400  # 与原 startTime 比较
    r = client.put(f"{API}/transcripts/nope/text", json={"text": "x"})
    assert r.status_code == 404 and r.json()["code"] == 404


def test_speakers_scenes_default_without_llm(client, tmp_path):
    upload(client, tmp_path, audio_id="a1")
    wait_task(client, "a1")
    sp = client.get(f"{API}/audios/a1/speakers").json()["data"]
    assert [s["trackId"] for s in sp["speakers"]] == ["A", "B"]
    assert all(s["identity"] == "unknown" for s in sp["speakers"])
    assert [s["role"] for s in sp["speakers"]] == ["agent", "customer"]
    sc = client.get(f"{API}/audios/a1/scenes").json()["data"]
    assert sc["scenes"] == [] and sc["analysis"] is None and sc["callType"] == "unknown"
    tr = client.get(f"{API}/audios/a1/translations").json()["data"]
    assert tr["status"] == "completed" and tr["items"] == [] and tr["targetLanguage"] == "en"


def test_mono_has_single_speaker(client, tmp_path):
    upload(client, tmp_path, name="m.wav", audio_id="m1", maker=make_mono)
    items = wait_task(client, "m1").json()["data"]["items"]
    assert [i["trackId"] for i in items] == ["A"]
    assert [s["trackId"] for s in client.get(f"{API}/audios/m1/speakers").json()["data"]["speakers"]] == ["A"]


def test_llm_identity_scenes_translations(make_client, tmp_path):
    llm = FakeLlm()
    c = make_client(llm=llm)
    upload(c, tmp_path, audio_id="a1")
    wait_task(c, "a1")
    sp = c.get(f"{API}/audios/a1/speakers").json()["data"]["speakers"]
    assert sp[0]["identity"] == "运营商客服人员" and sp[0]["role"] == "agent" and sp[0]["confidence"] == 0.8
    assert sp[1]["identity"] == "客户" and sp[1]["emotionDistribution"] == {}
    sc = c.get(f"{API}/audios/a1/scenes").json()["data"]
    assert sc["scenes"][0]["description"] == "技术支持通话" and sc["callType"] == "inbound"
    assert sc["analysis"] == {"hasComplaint": True, "complaintScore": 0.5, "hasPraise": False, "isEscalated": False}

    # 默认语种（en）在流水线中预翻译
    tr = c.get(f"{API}/audios/a1/translations").json()["data"]
    assert [t["text"] for t in tr["items"]][0].startswith("[en] ")
    assert {t["transcriptId"] for t in tr["items"]} == {
        i["id"] for i in c.get(f"{API}/audios/a1/transcripts").json()["data"]["items"]}
    calls = llm.translate_calls
    c.get(f"{API}/audios/a1/translations")
    assert llm.translate_calls == calls  # 已有译文不重复翻译
    # 其它语种按需翻译
    ja = c.get(f"{API}/audios/a1/translations", params={"language": "ja", "track": "B"}).json()["data"]
    assert ja["targetLanguage"] == "ja" and [t["trackId"] for t in ja["items"]] == ["B"]
    assert c.get(f"{API}/audios/a1/translations", params={"language": "!!"}).status_code == 400

    # 译文编辑落库
    tid = tr["items"][0]["id"]
    r = c.put(f"{API}/translations/{tid}", json={"text": "Edited"}).json()
    assert r["message"] == "翻译内容更新成功" and r["data"]["text"] == "Edited"
    assert c.get(f"{API}/audios/a1/translations").json()["data"]["items"][0]["text"] == "Edited"
    assert c.put(f"{API}/translations/nope", json={"text": "x"}).status_code == 404


def test_llm_failure_does_not_break_transcription(make_client, tmp_path):
    from app.services.llm import LlmError

    class Broken(FakeLlm):
        def analyze(self, *a, **k):
            raise LlmError("boom")

        def translate(self, *a, **k):
            raise LlmError("boom")

    c = make_client(llm=Broken())
    upload(c, tmp_path, audio_id="a1")
    assert wait_task(c, "a1").json()["data"]["status"] == "completed"
    assert c.get(f"{API}/audios/a1/speakers").json()["data"]["speakers"][0]["identity"] == "unknown"


def test_websocket_events(client, tmp_path):
    with client.websocket_connect("/ws") as ws:
        upload(client, tmp_path, audio_id="a1")
        seen = {}
        deadline = time.time() + 10
        while "transcription_completed" not in seen and time.time() < deadline:
            msg = ws.receive_json()
            seen[msg["type"]] = msg
    assert seen["peaks_generated"]["audioId"] == "a1" and seen["peaks_generated"]["status"] == "completed"
    done = seen["transcription_completed"]
    assert done["transcriptCount"] == 2 and done["status"] == "completed" and done["taskId"]
    if "transcription_progress" in seen:
        p = seen["transcription_progress"]
        assert 0 <= p["progress"] <= 100 and p["status"] == "processing"
