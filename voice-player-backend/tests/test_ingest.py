import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest

from conftest import make_mono, make_stereo, upload, wait_task

API = "/api/v1/audios"


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture
def www(tmp_path):
    """本地文件服务，模拟入库系统的下载地址。返回 (目录, 根地址)。"""
    root = tmp_path / "www"
    root.mkdir()
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield root, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


@pytest.fixture
def ingest_client(make_client):
    return make_client(ingest_allowed_hosts="127.0.0.1")


def ingest(client, audio_id, url, **extra):
    return client.post(f"{API}/{audio_id}/ingest", json={"source": {"type": "url", "url": url, **extra.pop("source", {})}, **extra})


def test_ingest_downloads_and_starts_processing(ingest_client, www, tmp_path):
    root, base = www
    make_stereo(root / "call.wav")
    r = ingest(ingest_client, "x1", f"{base}/call.wav")
    body = r.json()
    assert r.status_code == 200 and body["code"] == 0
    assert body["data"] == {"audioId": "x1", "duration": 8.0, "sampleRate": 16000, "channels": 2, "alreadyIngested": False}
    audio_dir = tmp_path / "data" / "audios"
    assert [p.name for p in audio_dir.iterdir()] == ["x1.wav"]  # 不留 .part
    # 入库后与上传一样：能取到波形、能触发转写
    assert set(ingest_client.get(f"{API}/x1/peaks").json()["data"]["tracks"]) == {"A", "B"}
    wait_task(ingest_client, "x1")
    items = ingest_client.get(f"{API}/x1/transcripts").json()["data"]["items"]
    assert {i["trackId"] for i in items} == {"A", "B"}


def test_ingest_is_idempotent(ingest_client, www):
    root, base = www
    make_stereo(root / "call.wav")
    ingest(ingest_client, "x1", f"{base}/call.wav")
    (root / "call.wav").unlink()  # 源文件没了，重复调用也不应再下载
    r = ingest(ingest_client, "x1", f"{base}/call.wav")
    assert r.status_code == 200 and r.json()["data"]["alreadyIngested"] is True


def test_ingest_force_replaces_audio_and_results(ingest_client, www):
    root, base = www
    make_stereo(root / "old.wav")
    make_mono(root / "new.wav")
    ingest(ingest_client, "x1", f"{base}/old.wav")
    wait_task(ingest_client, "x1")
    r = ingest(ingest_client, "x1", f"{base}/new.wav", force=True)
    assert r.status_code == 200 and r.json()["data"]["alreadyIngested"] is False
    assert r.json()["data"]["channels"] == 1
    assert set(ingest_client.get(f"{API}/x1/peaks").json()["data"]["tracks"]) == {"A"}  # 旧的双轨缓存已清


def test_ingest_force_failed_download_keeps_existing(ingest_client, www):
    root, base = www
    make_stereo(root / "old.wav")
    ingest(ingest_client, "x1", f"{base}/old.wav")
    r = ingest(ingest_client, "x1", f"{base}/missing.wav", force=True)
    assert r.status_code == 502
    assert ingest_client.get(f"{API}/x1/peaks").status_code == 200  # 旧音频还在


def test_ingest_force_rejected_while_processing(ingest_client, www):
    root, base = www
    make_stereo(root / "call.wav")
    ingest(ingest_client, "x1", f"{base}/call.wav")
    wait_task(ingest_client, "x1")
    ingest_client.app.state.pipeline._inflight.add("x1")
    try:
        r = ingest(ingest_client, "x1", f"{base}/call.wav", force=True)
        assert r.status_code == 409
    finally:
        ingest_client.app.state.pipeline._inflight.discard("x1")


def test_ingest_concurrent_same_id_rejected(ingest_client, www):
    from app.routers import audios
    root, base = www
    make_stereo(root / "call.wav")
    audios._ingesting.add("x1")
    try:
        assert ingest(ingest_client, "x1", f"{base}/call.wav").status_code == 409
    finally:
        audios._ingesting.discard("x1")


def test_ingest_url_must_be_allowed(make_client, www):
    root, base = www
    make_stereo(root / "call.wav")
    assert ingest(make_client(), "x1", f"{base}/call.wav").status_code == 403  # 默认不允许任何地址
    c = make_client(ingest_allowed_hosts="storage.internal")
    assert ingest(c, "x1", f"{base}/call.wav").status_code == 403
    assert ingest(c, "x1", "file:///etc/passwd").status_code == 400
    assert ingest(c, "x1", "ftp://storage.internal/a.wav").status_code == 400


def test_ingest_upstream_errors(make_client, www, tmp_path):
    root, base = www
    c = make_client(ingest_allowed_hosts="127.0.0.1")
    assert ingest(c, "x1", f"{base}/missing.wav").status_code == 502
    assert ingest(c, "x1", "http://127.0.0.1:1/a.wav").status_code == 502  # 连不上
    (root / "empty.wav").write_bytes(b"")
    assert ingest(c, "x1", f"{base}/empty.wav").status_code == 400
    (root / "bad.wav").write_bytes(b"not audio")
    r = ingest(c, "x1", f"{base}/bad.wav")
    assert r.json()["code"] == 50002  # 后缀合法但内容损坏
    assert not list((tmp_path / "data" / "audios").iterdir())  # 失败不留残留


def test_ingest_too_large(make_client, www):
    root, base = www
    make_stereo(root / "call.wav")
    c = make_client(ingest_allowed_hosts="127.0.0.1", max_upload_bytes=1000)
    r = ingest(c, "x1", f"{base}/call.wav")
    assert r.status_code == 413 and r.json()["code"] == 40004


def test_ingest_format_detection(ingest_client, www):
    root, base = www
    make_stereo(root / "tmp.wav")
    (root / "tmp.wav").rename(root / "blob")  # 没有后缀，Content-Type 也无法识别
    assert ingest(ingest_client, "x1", f"{base}/blob").status_code == 415
    r = ingest(ingest_client, "x1", f"{base}/blob", source={"ext": "wav"})
    assert r.status_code == 200 and r.json()["data"]["channels"] == 2


def test_ingest_validates_audio_id(ingest_client, www):
    root, base = www
    make_stereo(root / "call.wav")
    assert ingest(ingest_client, "bad id", f"{base}/call.wav").status_code == 400


def test_upload_can_be_disabled(make_client, tmp_path):
    c = make_client(upload_enabled=False)
    r = upload(c, tmp_path, audio_id="a1")
    assert r.status_code == 403 and "ingest" in r.json()["message"]
