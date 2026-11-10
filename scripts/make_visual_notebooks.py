"""Write the Colab notebooks that show the block editor: 02_rationing_visual_<lang>.ipynb.

    python scripts/make_visual_notebooks.py                  # for the published course (branch main)
    python scripts/make_visual_notebooks.py --branch my-work # to try a branch in Colab before it is merged

The notebooks hold no logic of their own: a setup cell and one cell that shows the editor.
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/hydrosolutions/zarafshan-taqsim-course.git"

TEXT = {
    "en": {
        "title": "# A reservoir and a farm, built with blocks\n\n*Step 2 of the course without writing code*\n\n"
        "Run the two cells below with the ▶ button, one after the other. The first takes about a minute. "
        "Then build the model in the drawing area: drag blocks, connect them and move the sliders. "
        "TaqSim recalculates after every change.\n\n"
        "Prefer code? The same lesson as a coding notebook is `02_rationing_en.ipynb`.",
        "setup": "Setup: run this cell first",
        "show": "The block editor: run this cell, then work in the drawing area",
    },
}

SETUP = '''# @title {title}
import os
import subprocess
import sys

BRANCH = "{branch}"
if not os.path.exists("src/zarafshan_taqsim"):  # not inside the course folder yet (the normal case in Colab)
    if not os.path.exists("zarafshan-taqsim-course"):
        subprocess.run(["git", "clone", "-q", "--depth", "1", "-b", BRANCH, "{repo}"], check=True)
    os.chdir("zarafshan-taqsim-course")
if os.path.exists(".git"):
    subprocess.run(["git", "pull", "-q", "--ff-only"], check=False)
for name in [m for m in sys.modules if m == "zarafshan_taqsim" or m.startswith("zarafshan_taqsim.")]:
    del sys.modules[name]
try:
    import taqsim  # noqa: F401  (already installed when you work on your own computer)
except ImportError:
    %pip install -q deap ctrl-freak pymoo
    %pip install -q --no-deps "git+https://github.com/hydrosolutions/taqsim.git@v0.1.4"
try:
    import anywidget  # noqa: F401
except ImportError:
    %pip install -q anywidget
try:
    from google.colab import output  # only exists in Colab, where widgets from packages must be switched on

    output.enable_custom_widget_manager()
except ImportError:
    pass
sys.path[:0] = [os.path.abspath("src")]
print("Ready.")'''

SHOW = '''# @title {title}
from zarafshan_taqsim.block_editor import BlockEditor

BlockEditor(lang="{lang}")'''


def cell(kind: str, source: str, form: bool = False) -> dict:
    lines = source.split("\n")
    body = {"cell_type": kind, "metadata": {"cellView": "form"} if form else {}, "source": [line + "\n" for line in lines[:-1]] + [lines[-1]]}
    if kind == "code":
        body |= {"execution_count": None, "outputs": []}
    return body


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", default="main")
    branch = parser.parse_args().branch
    for lang, text in TEXT.items():
        name = f"02_rationing_visual_{lang}.ipynb"
        notebook = {
            "cells": [
                cell("markdown", text["title"]),
                cell("code", SETUP.format(title=text["setup"], branch=branch, repo=REPO), form=True),
                cell("code", SHOW.format(title=text["show"], lang=lang), form=True),
            ],
            "metadata": {
                "colab": {"name": name, "provenance": []},
                "kernelspec": {"display_name": "Python 3 (ipykernel)", "language": "python", "name": "python3"},
            },
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        (ROOT / name).write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {name} (branch {branch})")


if __name__ == "__main__":
    main()
