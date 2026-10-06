"""Assemble the offline e-flow game into one self-contained HTML file.

Usage: uv run --project workshop/eflow_game python -m eflow_game.build

The page is built from workshop/eflow_game/game/{template.html,style.css,model.js,app.js} and the precomputed
eflow_game_data.json (written by ``python -m eflow_game.model``). The page carries every plan of the grid with its
TaqSim crop supply and its fishy river score, the natural daily flow of the five scored years, and a JavaScript twin
of the two rules for the charts.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

GAME_DIR = Path(__file__).resolve().parents[2]
DATA_FILE = GAME_DIR / "eflow_game_data.json"
OUTPUT_FILE = GAME_DIR / "eflow_game.html"
SOURCES = ("template.html", "style.css", "model.js", "app.js")
PLACEHOLDERS = {"/*__STYLE__*/": "style.css", "/*__MODEL__*/": "model.js", "/*__APP__*/": "app.js"}


def _script_safe(source: str) -> str:
    return source.replace("</", "<\\/")


def page_data(data: dict) -> dict:
    """What the browser needs: everything in the export except the per-plan list of plans that beat it."""
    plans = [{k: v for k, v in plan.items() if k != "beaten_by"} for plan in data["plans"]]
    return {k: v for k, v in data.items() if k != "plans"} | {"plans": plans}


def build(game_dir: Path = GAME_DIR, data_file: Path = DATA_FILE, output_file: Path = OUTPUT_FILE) -> Path:
    """Inline styles, data and scripts into a single HTML file that works without a network."""
    source = game_dir / "game"
    data = json.loads(data_file.read_text())
    parts = {placeholder: _script_safe((source / name).read_text()) for placeholder, name in PLACEHOLDERS.items()}
    parts["/*__DATA__*/"] = _script_safe(json.dumps(page_data(data), separators=(",", ":")))
    page = (source / "template.html").read_text()
    for placeholder, content in parts.items():
        if page.count(placeholder) != 1:
            raise ValueError(f"template must contain {placeholder} exactly once")
        page = page.replace(placeholder, content)
    output_file.write_text(page)
    logger.info("wrote %s (%.0f kB)", output_file, output_file.stat().st_size / 1024)
    return output_file


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    build()
