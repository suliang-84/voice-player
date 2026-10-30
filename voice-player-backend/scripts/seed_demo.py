"""把仓库里带的演示音频（demo/）复制到 DATA_DIR/audios，供播放器演示页使用。
已存在同名 audioId 的音频会跳过。用法：.venv/bin/python scripts/seed_demo.py"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import get_settings  # noqa: E402

DEMO_DIR = ROOT / "demo"


def main() -> None:
    out_dir = get_settings().audio_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    for src in sorted(DEMO_DIR.glob("*.flac")):
        if any(out_dir.glob(f"{src.stem}.*")):
            print(f"skip   {src.stem}（已存在）")
            continue
        shutil.copy2(src, out_dir / src.name)
        print(f"copied {out_dir / src.name}")


if __name__ == "__main__":
    main()
