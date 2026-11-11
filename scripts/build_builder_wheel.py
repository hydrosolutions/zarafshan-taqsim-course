"""Pack the block editor and the rationing helpers into the small wheel the browser page installs.

    python scripts/build_builder_wheel.py

The full `zarafshan_taqsim` package imports libraries that do not run in the browser, so the wheel carries a
reduced `__init__` and only the modules the editor needs (the same approach as the taqsim-blocks page).
"""

import base64
import csv
import hashlib
import io
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "zarafshan_taqsim"
VERSION = "0.1.0+wasm.builder"
WHEEL = ROOT / "interactive" / "rationing-builder" / "wheels" / f"zarafshan_taqsim-{VERSION}-py3-none-any.whl"
DIST = f"zarafshan_taqsim-{VERSION}.dist-info"


def main() -> None:
    files: dict[str, bytes] = {
        "zarafshan_taqsim/__init__.py": b'"""Reduced package for the block editor page only."""\n',
        "zarafshan_taqsim/rationing_coursebook.py": (SRC / "rationing_coursebook.py").read_bytes(),
        "zarafshan_taqsim/blocks_demo.py": (SRC / "blocks_demo.py").read_bytes(),
    }
    for path in sorted((SRC / "block_editor").iterdir()):
        if path.suffix in {".py", ".js", ".css", ".json"}:
            files[f"zarafshan_taqsim/block_editor/{path.name}"] = path.read_bytes()
    files[f"{DIST}/WHEEL"] = b"Wheel-Version: 1.0\nGenerator: build_builder_wheel\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    files[f"{DIST}/METADATA"] = (
        f"Metadata-Version: 2.3\nName: zarafshan-taqsim\nVersion: {VERSION}\n"
        "Requires-Dist: numpy\nRequires-Dist: pandas\nRequires-Dist: matplotlib\nRequires-Dist: anywidget\n"
        "Requires-Dist: taqsim==0.1.4\nRequires-Python: >=3.12\n"
    ).encode()
    record = io.StringIO()
    writer = csv.writer(record, lineterminator="\n")
    for name, data in files.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
        writer.writerow([name, f"sha256={digest}", len(data)])
    writer.writerow([f"{DIST}/RECORD", "", ""])
    files[f"{DIST}/RECORD"] = record.getvalue().encode()
    WHEEL.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(WHEEL, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            # A fixed date keeps the wheel identical when nothing changed
            archive.writestr(zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0)), data, zipfile.ZIP_DEFLATED)
    print(f"wrote {WHEEL.relative_to(ROOT)} ({WHEEL.stat().st_size / 1024:.0f} KB, {len(files)} files)")


if __name__ == "__main__":
    main()
