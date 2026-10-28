"""播放器打开时，/stream、peaks 与后台转写会同时请求同一批派生文件，必须互不影响。"""
import threading
from concurrent.futures import ThreadPoolExecutor

import soundfile as sf

from app.config import Settings
from app.services import audio
from app.services.peaks_cache import get_peaks
from app.services.storage import Storage
from conftest import make_stereo, upload, wait_task

API = "/api/v1/audios"


def make_storage(tmp_path) -> Storage:
    settings = Settings(data_dir=tmp_path / "data")
    settings.ensure_dirs()
    make_stereo(settings.audio_dir / "a1.wav")
    return Storage(settings)


def run_parallel(fn, n=16):
    barrier = threading.Barrier(n)

    def task(_):
        barrier.wait()
        return fn()

    with ThreadPoolExecutor(n) as pool:
        return list(pool.map(task, range(n)))


def test_track_wav_built_once_and_valid_under_concurrency(tmp_path, monkeypatch):
    storage = make_storage(tmp_path)
    builds = []
    real = audio.extract_channel
    monkeypatch.setattr(audio, "extract_channel", lambda *a: (builds.append(1), real(*a))[1])

    paths = run_parallel(lambda: storage.track_wav("a1", "A"))
    assert len(set(paths)) == 1 and len(builds) == 1  # 只生成一次，其余线程复用
    info = sf.info(paths[0])
    assert info.channels == 1 and abs(info.duration - 8) < 0.01
    cache = storage.cache_dir("a1")
    assert [p.name for p in cache.iterdir() if ".tmp" in p.name] == []  # 不留临时文件


def test_both_tracks_and_peaks_concurrently(tmp_path):
    storage = make_storage(tmp_path)
    jobs = [lambda: storage.track_wav("a1", "A"), lambda: storage.track_wav("a1", "B"),
            lambda: get_peaks(storage.settings, storage, "a1", 100)]
    results = run_parallel(lambda: [j() for j in jobs], n=12)
    assert all(r[2]["tracks"].keys() == {"A", "B"} for r in results)
    for tid in "AB":
        assert sf.info(storage.track_wav("a1", tid)).channels == 1


def test_failed_build_leaves_no_partial_cache(tmp_path):
    storage = make_storage(tmp_path)
    src = storage.source_wav("a1")
    cache = storage.cache_dir("a1") / "x.bin"

    def boom(tmp):
        tmp.write_bytes(b"partial")
        raise RuntimeError("boom")

    try:
        storage.build_cached(cache, src, boom)
    except RuntimeError:
        pass
    assert not cache.exists() and list(cache.parent.glob("*.tmp*")) == []
    storage.build_cached(cache, src, lambda tmp: tmp.write_bytes(b"ok"))  # 失败后可重新生成
    assert cache.read_bytes() == b"ok"


def test_stream_while_transcription_runs(client, tmp_path):
    """upload 立即触发转写（要生成声道文件），同时多个 /stream 请求到来：全部成功且是合法 WAV。"""
    upload(client, tmp_path, audio_id="a1")

    def get(track):
        r = client.get(f"{API}/a1/stream", params={"track": track})
        return r.status_code, r.content

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(get, ["A", "B"] * 4))
    assert [code for code, _ in results] == [200] * 8
    out = tmp_path / "t.wav"
    for _, body in results:
        out.write_bytes(body)
        assert sf.info(out).channels == 1
    assert wait_task(client, "a1").json()["data"]["status"] == "completed"
