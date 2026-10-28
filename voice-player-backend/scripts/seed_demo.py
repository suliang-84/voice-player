"""把前端 public/demo-a.wav、demo-b.wav 合成立体声（A=左，B=右），放进 DATA_DIR/audios，
作为演示页使用的 audio_001 / audio_002。用法：.venv/bin/python scripts/seed_demo.py"""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import get_settings  # noqa: E402

PUBLIC = ROOT.parent / "voice-player-frontend" / "public"
# audioId → 截取的秒数（None 为全长）；audio_002 用较短的片段，省空间
DEMOS = {"audio_001": None, "audio_002": 120}


def main() -> None:
    out_dir = get_settings().audio_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    a, sr = sf.read(PUBLIC / "demo-a.wav", dtype="float32", always_2d=True)
    b, sr_b = sf.read(PUBLIC / "demo-b.wav", dtype="float32", always_2d=True)
    assert sr == sr_b, "demo-a / demo-b 采样率不一致"
    for audio_id, seconds in DEMOS.items():
        target = out_dir / f"{audio_id}.wav"
        if target.exists():
            print(f"skip   {target}（已存在）")
            continue
        n = min(len(a), len(b)) if seconds is None else min(len(a), len(b), seconds * sr)
        sf.write(target, np.stack([a[:n, 0], b[:n, 0]], axis=1), sr, subtype="PCM_16")
        print(f"wrote  {target}  {n / sr:.0f}s")


if __name__ == "__main__":
    main()
