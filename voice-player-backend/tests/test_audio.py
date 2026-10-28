import soundfile as sf

from conftest import make_mono, upload

API = "/api/v1/audios"


def test_upload_returns_info(client, tmp_path):
    r = upload(client, tmp_path, audio_id="a1")
    body = r.json()
    assert r.status_code == 200 and body["code"] == 0
    assert body["data"] == {"audioId": "a1", "duration": 8.0, "sampleRate": 16000, "channels": 2}
    assert "timestamp" in body


def test_upload_rejects_bad_input(client, tmp_path):
    upload(client, tmp_path, audio_id="dup")
    assert upload(client, tmp_path, audio_id="dup").json()["code"] == 400  # 重复
    assert client.post(API, files={"file": ("x.txt", b"hi")}).json()["code"] == 40003  # 后缀
    assert client.post(API, files={"file": ("x.wav", b"not audio")}).json()["code"] == 50002  # 后缀合法但内容损坏
    assert client.post(API, files={"file": ("x.wav", b"")}).json()["code"] == 400  # 空
    bad = client.post(API, files={"file": ("x.wav", b"x")}, data={"audioId": "../evil"})
    assert bad.json()["code"] == 400
    assert [p.name for p in (tmp_path / "data" / "audios").iterdir()] == ["dup.wav"]  # 失败的上传不留残留


def test_upload_too_large(make_client, tmp_path):
    c = make_client(max_upload_bytes=1000)
    r = upload(c, tmp_path)
    assert r.status_code == 413 and r.json()["code"] == 40004


def test_missing_audio_is_40001(client):
    r = client.get(f"{API}/nope/peaks")
    assert r.status_code == 404 and r.json()["code"] == 40001


def test_peaks_contract(client, tmp_path):
    upload(client, tmp_path, audio_id="a1")
    d = client.get(f"{API}/a1/peaks", params={"maxLength": 100, "precision": 1}).json()["data"]
    assert d["duration"] == 8.0 and d["sampleRate"] == 16000
    assert set(d["tracks"]) == {"A", "B"}
    for tid, amp in (("A", 0.5), ("B", 0.3)):
        t = d["tracks"][tid]
        assert len(t["peaks"]) == 1 and len(t["peaks"][0]) == t["pointCount"] <= 100
        assert max(abs(v) for v in t["peaks"][0]) <= amp + 0.05
    # A 轨 2~4s 静音 → 对应点为 0；B 轨无 0 段
    a = d["tracks"]["A"]["peaks"][0]
    n = len(a)
    assert all(v == 0 for v in a[int(n * 0.3):int(n * 0.45)])
    assert any(abs(v) > 0.2 for v in a[:int(n * 0.2)])
    assert all(v != 0 for v in d["tracks"]["B"]["peaks"][0][5:-5])


def test_peaks_single_track_and_validation(client, tmp_path):
    upload(client, tmp_path, audio_id="a1")
    d = client.get(f"{API}/a1/peaks", params={"track": "B"}).json()["data"]
    assert set(d["tracks"]) == {"B"}
    assert client.get(f"{API}/a1/peaks", params={"track": "C"}).status_code == 400
    assert client.get(f"{API}/a1/peaks", params={"maxLength": 0}).status_code == 400


def test_peaks_mono_only_track_a(client, tmp_path):
    upload(client, tmp_path, name="m.wav", audio_id="m1", maker=make_mono)
    d = client.get(f"{API}/m1/peaks").json()["data"]
    assert set(d["tracks"]) == {"A"}
    assert client.get(f"{API}/m1/peaks", params={"track": "B"}).status_code == 400


def test_silences(client, tmp_path):
    upload(client, tmp_path, audio_id="a1")
    d = client.get(f"{API}/a1/silences").json()["data"]["tracks"]
    a = d["A"]["silences"]
    assert len(a) == 1 and abs(a[0]["start"] - 2.0) < 0.05 and abs(a[0]["end"] - 4.0) < 0.05
    assert abs(a[0]["duration"] - (a[0]["end"] - a[0]["start"])) < 1e-6
    assert abs(d["A"]["silencePercentage"] - 25.0) < 1
    assert d["B"]["silences"] == [] and d["B"]["totalSilenceDuration"] == 0
    only_b = client.get(f"{API}/a1/silences", params={"track": "B"}).json()["data"]["tracks"]
    assert set(only_b) == {"B"}
    # minDuration 大于静音长度 → 被忽略
    long = client.get(f"{API}/a1/silences", params={"minDuration": 5}).json()["data"]["tracks"]
    assert long["A"]["silences"] == []


def test_stream_mono_wav_with_range(client, tmp_path):
    upload(client, tmp_path, audio_id="a1")
    full = client.get(f"{API}/a1/stream", params={"track": "B"})
    assert full.status_code == 200 and full.headers["content-type"] == "audio/wav"
    assert full.headers["accept-ranges"] == "bytes"
    out = tmp_path / "b.wav"
    out.write_bytes(full.content)
    info = sf.info(out)
    assert info.channels == 1 and info.samplerate == 16000 and abs(info.duration - 8) < 0.01
    data, _ = sf.read(out)
    assert abs(data).max() < 0.35  # B 轨幅度 0.3，而非 A 轨 0.5

    part = client.get(f"{API}/a1/stream", params={"track": "A"}, headers={"Range": "bytes=0-99"})
    assert part.status_code == 206 and len(part.content) == 100
    assert part.headers["content-range"].startswith("bytes 0-99/")


def test_stream_validation(client, tmp_path):
    upload(client, tmp_path, name="m.wav", audio_id="m1", maker=make_mono)
    assert client.get(f"{API}/m1/stream", params={"track": "A"}).status_code == 200
    assert client.get(f"{API}/m1/stream", params={"track": "B"}).status_code == 400
    assert client.get(f"{API}/zz/stream").status_code == 404
    assert client.get(f"{API}/m1/stream", params={"track": "X"}).status_code == 400


def test_non_wav_is_transcoded(client, tmp_path):
    import shutil, subprocess
    if not shutil.which("ffmpeg"):
        return
    wav = tmp_path / "s.wav"
    from conftest import make_stereo
    make_stereo(wav, seconds=2)
    m4a = tmp_path / "s.m4a"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), str(m4a)], check=True)
    with m4a.open("rb") as f:
        r = client.post("/api/v1/audios", files={"file": ("s.m4a", f)}, data={"audioId": "m4a1"})
    assert r.json()["code"] == 0 and r.json()["data"]["channels"] == 2
    assert client.get(f"{API}/m4a1/peaks").json()["code"] == 0
