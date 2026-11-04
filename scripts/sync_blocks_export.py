"""Sync the checked-in Marimo source and helper into the existing WASM export.

Run with Python 3.12+. Retains the export's runtime assets; does not re-export Marimo.
"""
from pathlib import Path
import base64
import csv
import hashlib
import io
import json
import re
import urllib.parse
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'interactive/taqsim-blocks'
source = (PAGE / 'notebook.py').read_text()
html = (PAGE / 'index.html').read_text()
html, count = re.subn(r'(notebookCode:\s*)"(?:\\.|[^"\\])*"', lambda m: m[1] + json.dumps(source, ensure_ascii=False), html, count=1)
assert count == 1, 'Missing export context'
html, count = re.subn(r'(<marimo-code[^>]*>).*?(</marimo-code>)', lambda m: m[1] + urllib.parse.quote(source, safe='') + m[2], html, flags=re.S)
assert count == 1, 'Missing embedded source'
(PAGE / 'index.html').write_text(html)
wheel = PAGE / 'wheels/zarafshan_taqsim-0.1.0+wasm.catalogue20261013-py3-none-any.whl'
with zipfile.ZipFile(wheel) as archive:
    files = {name: archive.read(name) for name in archive.namelist()}
key = next(name for name in files if name.endswith('/blocks_demo.py'))
files[key] = (ROOT / 'src/zarafshan_taqsim/blocks_demo.py').read_bytes()
record = next(name for name in files if name.endswith('.dist-info/RECORD'))
output = io.StringIO()
writer = csv.writer(output, lineterminator='\n')
for name, data in files.items():
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('=')
    writer.writerow([name, '' if name == record else 'sha256=' + digest, '' if name == record else len(data)])
files[record] = output.getvalue().encode()
with zipfile.ZipFile(wheel, 'w', zipfile.ZIP_DEFLATED) as archive:
    for name, data in files.items():
        archive.writestr(name, data)
