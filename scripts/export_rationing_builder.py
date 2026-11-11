"""Export the block editor page to interactive/rationing-builder/ so that GitHub Pages can serve it.

    uv run --with marimo==0.25.2 --with anywidget python scripts/export_rationing_builder.py

It packs the wheel the page installs, lets marimo export the notebook as a page that runs Python in the browser,
and puts the page, marimo's assets and the wheels side by side. Run it again after any change to
`src/zarafshan_taqsim/block_editor/`, `rationing_coursebook.py` or the notebook.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "interactive" / "rationing-builder"
TAQSIM_WHEEL = ROOT / "interactive" / "taqsim-blocks" / "wheels" / "taqsim-0.1.4-py3-none-any.whl"
KEEP = {"notebook.py", "wheels"}  # ours; everything else in the folder comes from the export
SKIP = {"CLAUDE.md"}  # marimo's note for coding assistants; not part of the page


def main() -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_builder_wheel.py")], check=True)
    with tempfile.TemporaryDirectory() as scratch:
        out = Path(scratch) / "page"
        subprocess.run(
            [sys.executable, "-m", "marimo", "export", "html-wasm", str(PAGE / "notebook.py"), "-o", str(out), "--mode", "run"],
            check=True,
        )
        for old in PAGE.iterdir():
            if old.name not in KEEP:
                shutil.rmtree(old) if old.is_dir() else old.unlink()
        for new in out.iterdir():
            if new.name in SKIP or new.name in KEEP:
                continue
            shutil.copytree(new, PAGE / new.name) if new.is_dir() else shutil.copy2(new, PAGE / new.name)
    shutil.copy2(TAQSIM_WHEEL, PAGE / "wheels" / TAQSIM_WHEEL.name)
    size = sum(path.stat().st_size for path in PAGE.rglob("*") if path.is_file()) / 1e6
    print(f"exported to {PAGE.relative_to(ROOT)} ({size:.0f} MB)")


if __name__ == "__main__":
    main()
