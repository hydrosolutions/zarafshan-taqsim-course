"""Assemble the offline warm-up game into one self-contained HTML file.

Usage: uv run python -m zarafshan_taqsim.workshop.build_warmup

The page is built from workshop/warmup_game/game/{template.html,style.css,model.js,sketches.js,app.js} and the
exported warmup_game_data.json (written by `warmup_game.export_game_data`). Reference cases stay out of the page;
per year the page carries the grid positions of the plans that no other plan beats and re-runs them with its own
copy of the model.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

GAME_DIR = Path(__file__).resolve().parents[3] / "workshop" / "warmup_game"
DATA_FILE = GAME_DIR / "warmup_game_data.json"
OUTPUT_FILE = GAME_DIR / "zarafshan_warmup_game.html"
SOURCES = ("template.html", "style.css", "model.js", "sketches.js", "app.js")


def _script_safe(source: str) -> str:
    return source.replace("</", "<\\/")


def page_data(data: dict) -> dict:
    """Only what the browser needs: constants, metadata and, per year, the unbeaten plans and the optimiser check."""
    fronts = {
        year: {"front": front["front"], "grid_size": front["grid_size"], "optimiser": front["optimiser"]}
        for year, front in data["fronts"].items()
    }
    return {"meta": data["meta"], "constants": data["constants"], "fronts": fronts}


def build_warmup(game_dir: Path = GAME_DIR, data_file: Path = DATA_FILE, output_file: Path = OUTPUT_FILE) -> Path:
    """Inline styles, data and scripts into a single HTML file that works without a network."""
    source = game_dir / "game"
    data = json.loads(data_file.read_text())
    parts = {
        "/*__STYLE__*/": (source / "style.css").read_text(),
        "/*__DATA__*/": _script_safe(json.dumps(page_data(data), separators=(",", ":"))),
        "/*__MODEL__*/": _script_safe((source / "model.js").read_text()),
        "/*__SKETCHES__*/": _script_safe((source / "sketches.js").read_text()),
        "/*__APP__*/": _script_safe((source / "app.js").read_text()),
    }
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
    build_warmup()
