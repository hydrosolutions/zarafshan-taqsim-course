"""Write the Colab notebooks that show the block editor: 02_rationing_visual_<lang>.ipynb.

    python scripts/make_visual_notebooks.py

The notebooks hold no logic of their own: a setup cell and one cell that shows the editor. The setup cell
fetches the published course (branch main); while the editor is not published there yet, it takes the branch
it is being built on instead, so the same notebooks can be tried in Colab before and after the merge.
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/hydrosolutions/zarafshan-taqsim-course.git"

TEXT = {
    "en": {
        "title": "# A reservoir and a farm, built with blocks\n\n*Step 3 of the course without writing code*\n\n"
        "Run the two cells below with the ▶ button, one after the other. The first takes about a minute. "
        "Then build the model in the drawing area: drag blocks, connect them and move the sliders. "
        "TaqSim recalculates after every change.\n\n"
        "Prefer code? The same lesson as a coding notebook is `02_rationing_en.ipynb`.",
        "setup": "Setup: run this cell first",
        "show": "The block editor: run this cell, then work in the drawing area",
    },
    "ru": {
        "title": "# Водохранилище и хозяйство, собранные из блоков\n\n*Шаг 3 курса без написания кода*\n\n"
        "Запустите две ячейки ниже кнопкой ▶, одну за другой. Первая занимает около минуты. "
        "Затем соберите модель на поле: перетаскивайте блоки, соединяйте их и двигайте ползунки. "
        "TaqSim пересчитывает после каждого изменения.\n\n"
        "Предпочитаете код? Тот же урок в виде блокнота с кодом — `02_rationing_ru.ipynb`.",
        "setup": "Настройка: сначала запустите эту ячейку",
        "show": "Редактор блоков: запустите эту ячейку, затем работайте на поле",
    },
    "uz": {
        "title": "# Bloklardan qurilgan suv ombori va xoʻjalik\n\n*Kursning 3-qadami, kod yozmasdan*\n\n"
        "Pastdagi ikki katakni ▶ tugmasi bilan birin-ketin ishga tushiring. Birinchisi taxminan bir daqiqa oladi. "
        "Keyin modelni maydonda quring: bloklarni sudrang, ulang va surgichlarni suring. "
        "TaqSim har bir oʻzgarishdan keyin qayta hisoblaydi.\n\n"
        "Kodni afzal koʻrasizmi? Xuddi shu dars kodli daftar sifatida — `02_rationing_uz.ipynb`.",
        "setup": "Sozlash: avval shu katakni ishga tushiring",
        "show": "Bloklar muharriri: shu katakni ishga tushiring, keyin maydonda ishlang",
    },
}

SETUP = '''# @title {title}
import os
import subprocess
import sys

if not os.path.exists("src/zarafshan_taqsim"):  # not inside the course folder yet (the normal case in Colab)
    if not os.path.exists("zarafshan-taqsim-course"):
        subprocess.run(["git", "clone", "-q", "--depth", "1", "{repo}"], check=True)
    os.chdir("zarafshan-taqsim-course")
if os.path.exists(".git"):
    subprocess.run(["git", "pull", "-q", "--ff-only"], check=False)
    if not os.path.exists("src/zarafshan_taqsim/block_editor"):  # not published yet: take the branch it is built on
        subprocess.run(["git", "fetch", "-q", "--depth", "1", "origin", "{branch}"], check=True)
        subprocess.run(["git", "checkout", "-q", "FETCH_HEAD"], check=True)
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
    parser.add_argument("--preview-branch", default="janina/course-improvements", help="where the editor lives until it is on main")
    branch = parser.parse_args().preview_branch
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
        print(f"wrote {name}")


if __name__ == "__main__":
    main()
