"""流式音频算法：读取分块，内存不随音频长度增长。"""
import math
from pathlib import Path

import numpy as np
import soundfile as sf

BLOCK_FRAMES = 1 << 20


def info(path: Path) -> dict:
    i = sf.info(path)
    return {"duration": round(i.duration, 3), "sampleRate": i.samplerate, "channels": i.channels, "frames": i.frames}


def compute_peaks(path: Path, max_length: int) -> dict:
    """每个轨道 1 个声道，每个点取桶内绝对值最大的采样（保留符号）。返回 {轨道: [点...]}。"""
    with sf.SoundFile(path) as f:
        total, nch = f.frames, min(2, f.channels)
        if total == 0:
            return {"A": [], "B": []} if nch == 2 else {"A": []}
        points = max(1, min(max_length, total))
        bucket = math.ceil(total / points)
        rows_per_block = max(1, BLOCK_FRAMES // bucket)
        out: list[list[np.ndarray]] = [[] for _ in range(nch)]
        while True:
            data = f.read(rows_per_block * bucket, dtype="float32", always_2d=True)
            if len(data) == 0:
                break
            pad = (-len(data)) % bucket
            if pad:
                data = np.pad(data, ((0, pad), (0, 0)))
            for c in range(nch):
                x = data[:, c].reshape(-1, bucket)
                out[c].append(x[np.arange(len(x)), np.abs(x).argmax(axis=1)])
    ids = ("A", "B")
    return {ids[c]: np.concatenate(out[c]).tolist() for c in range(nch)}


def detect_silences(path: Path, threshold: float, min_duration: float, frame_ms: int) -> dict:
    """按声道逐帧 RMS 判静音，合并连续帧，过滤短于 min_duration 的段。"""
    with sf.SoundFile(path) as f:
        sr, nch, total = f.samplerate, min(2, f.channels), f.frames
        duration = total / sr if sr else 0.0
        frame = max(1, sr * frame_ms // 1000)
        block = frame * max(1, (sr * 10) // frame)
        flags: list[list[np.ndarray]] = [[] for _ in range(nch)]
        while True:
            data = f.read(block, dtype="float32", always_2d=True)
            if len(data) == 0:
                break
            pad = (-len(data)) % frame
            if pad:
                data = np.pad(data, ((0, pad), (0, 0)))
            for c in range(nch):
                x = data[:, c].reshape(-1, frame)
                flags[c].append(np.sqrt((x * x).mean(axis=1)) < threshold)
    result = {}
    for c, tid in enumerate(("A", "B")[:nch]):
        silent = np.concatenate(flags[c]) if flags[c] else np.zeros(0, dtype=bool)
        segs = _runs(silent, frame / sr, duration, min_duration)
        spent = round(sum(s["duration"] for s in segs), 3)
        result[tid] = {
            "silences": segs,
            "totalSilenceDuration": spent,
            "silencePercentage": round(spent / duration * 100, 1) if duration else 0.0,
        }
    return result


def _runs(silent: np.ndarray, frame_sec: float, duration: float, min_duration: float) -> list[dict]:
    if not len(silent):
        return []
    edges = np.diff(np.concatenate(([0], silent.astype(np.int8), [0])))
    starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    segs = []
    for s, e in zip(starts, ends):
        start, end = round(s * frame_sec, 3), round(min(e * frame_sec, duration), 3)
        if end - start >= min_duration and end > start:
            segs.append({"start": start, "end": end, "duration": round(end - start, 3)})
    return segs


def extract_channel(src: Path, channel: int, out: Path) -> None:
    """把指定声道写成单声道 PCM16 WAV（out 由调用方保证唯一，见 Storage.build_cached）。"""
    with sf.SoundFile(src) as f, sf.SoundFile(out, "w", samplerate=f.samplerate, channels=1,
                                              format="WAV", subtype="PCM_16") as w:
        while True:
            data = f.read(BLOCK_FRAMES, dtype="float32", always_2d=True)
            if len(data) == 0:
                break
            w.write(data[:, channel])
