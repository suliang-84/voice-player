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


def frame_rms(path: Path, frame_ms: int) -> tuple[np.ndarray, float, float]:
    """按声道逐帧 RMS。返回 (shape=[声道, 帧数] 的数组, 每帧秒数, 音频时长)。"""
    with sf.SoundFile(path) as f:
        sr, nch, total = f.samplerate, min(2, f.channels), f.frames
        duration = total / sr if sr else 0.0
        frame = max(1, sr * frame_ms // 1000)
        block = frame * max(1, (sr * 10) // frame)
        out: list[list[np.ndarray]] = [[] for _ in range(nch)]
        while True:
            data = f.read(block, dtype="float32", always_2d=True)
            if len(data) == 0:
                break
            pad = (-len(data)) % frame
            if pad:
                data = np.pad(data, ((0, pad), (0, 0)))
            for c in range(nch):
                x = data[:, c].reshape(-1, frame)
                out[c].append(np.sqrt((x * x).mean(axis=1)))
    rms = np.stack([np.concatenate(o) if o else np.zeros(0, dtype=np.float32) for o in out])
    return rms, frame / sr, duration


def smooth_rms(rms: np.ndarray, frames: int) -> np.ndarray:
    """滑动窗口能量平滑（居中窗口内取均方根）：数十毫秒的小杂音会被平均掉，持续的语音不受影响。"""
    if frames <= 1 or rms.size == 0:
        return rms
    power = np.concatenate(([0.0], np.cumsum(rms.astype(np.float64) ** 2)))
    idx = np.arange(len(rms))
    lo, hi = np.clip(idx - frames // 2, 0, len(rms)), np.clip(idx + (frames - frames // 2), 0, len(rms))
    return np.sqrt((power[hi] - power[lo]) / np.maximum(hi - lo, 1)).astype(np.float32)


def adaptive_threshold(rms: np.ndarray, margin_db: float, floor_db: float, ceil_db: float, percentile: float,
                       speech_offset_db: float = 25.0, speech_percentile: float = 90.0) -> float:
    """自适应阈值（RMS）。两个依据取较大者，再限制在 [floor_db, ceil_db]：
    · 底噪：低百分位帧能量 + margin_db；
    · 语音电平：高百分位帧能量 − speech_offset_db（比说话声低这么多的都算背景，
      解决「底噪估得太低、呼吸声和串音高于阈值」的问题）。"""
    if rms.size == 0:
        return 10 ** (floor_db / 20)
    db = lambda p: 20 * np.log10(max(float(np.percentile(rms, p)), 1e-7))
    thr_db = max(db(percentile) + margin_db, db(speech_percentile) - speech_offset_db)
    return float(10 ** (min(max(thr_db, floor_db), ceil_db) / 20))


def detect_silences(path: Path, threshold: float | None, min_duration: float, frame_ms: int, *,
                    min_speech: float = 0.3, padding: float = 0.15, margin_db: float = 12.0,
                    speech_offset_db: float = 25.0, smooth_ms: int = 150,
                    floor_db: float = -65.0, ceil_db: float = -35.0, noise_percentile: float = 10.0) -> dict:
    """静音检测。返回 {"tracks": {A/B: 单轨静音}, "both": 两路联合静音}。

    单轨：该声道逐帧 RMS 低于阈值，合并连续帧，过滤短于 min_duration 的段。
    联合：每一帧要 A、B 都低于各自阈值才算静音（单声道只看 A）；夹在静音之间、短于 min_speech 的
    零星有声帧（咳嗽、点击声）并入静音；短于 min_duration 的静音丢弃；留下的静音区间两端各缩进
    padding 秒，作为可跳过的范围，避免切掉词头词尾。activeSegments 是 [0, 时长] 去掉可跳过范围后的部分。
    逐帧 RMS 先做 smooth_ms 的滑动平滑再与阈值比较。
    threshold 为 None 时每个声道各自自适应（见 adaptive_threshold）；否则所有声道用同一个固定 RMS 阈值。"""
    rms, frame_sec, duration = frame_rms(path, frame_ms)
    rms = np.stack([smooth_rms(r, round(smooth_ms / 1000 / frame_sec)) for r in rms]) if len(rms) else rms
    ids = ("A", "B")[:len(rms)]
    thresholds = [
        adaptive_threshold(rms[c], margin_db, floor_db, ceil_db, noise_percentile, speech_offset_db)
        if threshold is None else threshold
        for c in range(len(rms))
    ]
    silent = [rms[c] < thresholds[c] for c in range(len(rms))]

    def summary(segs: list[dict]) -> dict:
        spent = round(sum(s["duration"] for s in segs), 3)
        return {"silences": segs, "totalSilenceDuration": spent,
                "silencePercentage": round(spent / duration * 100, 1) if duration else 0.0}

    tracks = {tid: summary(_runs(silent[c], frame_sec, duration, min_duration)) for c, tid in enumerate(ids)}

    joint = np.logical_and.reduce(silent) if silent else np.zeros(0, dtype=bool)
    joint = _fill_short_gaps(joint, max(1, round(min_speech / frame_sec)))
    skip = []
    for seg in _runs(joint, frame_sec, duration, min_duration):
        start = seg["start"] + (padding if seg["start"] > 0 else 0.0)
        end = seg["end"] - (padding if seg["end"] < duration - 1e-3 else 0.0)
        if end - start > 1e-3:
            skip.append({"start": round(start, 3), "end": round(end, 3), "duration": round(end - start, 3)})
    both = summary(skip)
    both["activeSegments"] = _complement(skip, duration)
    both["thresholdDb"] = {tid: round(20 * math.log10(max(thresholds[c], 1e-7)), 1) for c, tid in enumerate(ids)}
    return {"tracks": tracks, "both": both}


def _fill_short_gaps(silent: np.ndarray, max_frames: int) -> np.ndarray:
    """把夹在两段静音之间、不超过 max_frames 帧的有声帧改成静音（开头、结尾的有声帧不动）。"""
    if not len(silent):
        return silent
    out = silent.copy()
    edges = np.diff(np.concatenate(([0], (~silent).astype(np.int8), [0])))
    for s, e in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
        if s > 0 and e < len(silent) and e - s <= max_frames:
            out[s:e] = True
    return out


def _complement(segs: list[dict], duration: float) -> list[dict]:
    out, cursor = [], 0.0
    for s in segs:
        if s["start"] - cursor > 1e-3:
            out.append({"start": round(cursor, 3), "end": s["start"], "duration": round(s["start"] - cursor, 3)})
        cursor = s["end"]
    if duration - cursor > 1e-3:
        out.append({"start": round(cursor, 3), "end": round(duration, 3), "duration": round(duration - cursor, 3)})
    return out


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
