"""Assemble the offline "TaqSim block by block" game into one self-contained HTML file.

Usage: uv run python scripts/build_blocks_game.py   (or: uv run python -m zarafshan_taqsim.workshop.build_blocks_game)

The page is built from src/zarafshan_taqsim/blocks_game/{template.html,style.css,app.js}, the payload of
`blocks_demo.game_payload()` (every knob combination run through TaqSim) and, for the rule cards, the verbatim
source of the five rule classes and the wiring of each block as written in `blocks_demo.build_demo`. The
hydrosolutions logo is embedded as a small data URI so that the page makes no network request.
"""

from __future__ import annotations

import ast
import base64
import inspect
import io
import json
import logging
from pathlib import Path

from zarafshan_taqsim import blocks_demo
from zarafshan_taqsim.blocks_demo import (
    ANALOGY,
    BLOCK_KIND,
    KIND_COLOUR,
    LAYOUT,
    RULE_NAME,
    CanalShare,
    Evaporation,
    LagRouting,
    ReleaseTheNeed,
    SeepageLoss,
    game_payload,
)

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "zarafshan_taqsim" / "blocks_game"
LOGO_FILE = ROOT / "scripts" / "course_assets" / "hydrosolutions_logo.png"
OUTPUT_FILE = ROOT / "workshop" / "blocks_game" / "taqsim_blocks_game.html"
SOURCES = ("template.html", "style.css", "app.js")
PAGE_SIZE_BUDGET_BYTES = 700 * 1024
LOGO_HEIGHT_PX = 120

# The classes whose source each block's card shows, verbatim.
RULE_CLASSES: dict[str, tuple[type, ...]] = {
    "canyon": (LagRouting,),
    "headworks": (CanalShare,),
    "canal": (SeepageLoss,),
    "reservoir": (ReleaseTheNeed, Evaporation),
}
# Module-level constants shown above the wiring of the blocks that are configured by numbers rather than a class.
RULE_CONSTANTS: dict[str, tuple[str, ...]] = {
    "river": ("INFLOW_MM3",),
    "farm": ("FARM_NEED_MM3", "EFFICIENCY"),
}


def _script_safe(source: str) -> str:
    return source.replace("</", "<\\/")


def _module_tree() -> tuple[str, ast.Module]:
    source = inspect.getsource(blocks_demo)
    return source, ast.parse(source)


def _constant_lines(source: str, tree: ast.Module, names: tuple[str, ...]) -> list[str]:
    """The assignment of each named constant, with the comment line above it when there is one."""
    lines = source.splitlines()
    out = []
    for node in tree.body:
        target = (
            node.target
            if isinstance(node, ast.AnnAssign)
            else (node.targets[0] if isinstance(node, ast.Assign) else None)
        )
        if not isinstance(target, ast.Name) or target.id not in names:
            continue
        start = node.lineno - 1
        if start > 0 and lines[start - 1].lstrip().startswith("#"):
            start -= 1
        out.append("\n".join(lines[start : node.end_lineno]))
    return out


def _outdent(segment: str, columns: int) -> str:
    """A multi-line expression as it would be written at column 0: the first line starts there already."""
    first, *rest = segment.splitlines()
    return "\n".join([first, *(line[columns:] if line[:columns].isspace() else line for line in rest)])


def _wiring(source: str, tree: ast.Module) -> dict[str, str]:
    """For every block, the `Xxx(id="block", ...)` expression of `build_demo`, as written."""
    build = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "build_demo")
    wiring = {}
    for node in ast.walk(build):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        block_id = next(
            (kw.value.value for kw in node.keywords if kw.arg == "id" and isinstance(kw.value, ast.Constant)), None
        )
        if block_id in BLOCK_KIND:
            wiring[block_id] = _outdent(ast.get_source_segment(source, node) or "", node.col_offset)
    missing = set(BLOCK_KIND) - set(wiring)
    if missing:
        raise ValueError(f"no wiring found in build_demo for {sorted(missing)}")
    return wiring


def rule_sources() -> dict[str, str]:
    """What each block's rule card shows: the rule class(es) verbatim, the constants it reads, and how the block is wired."""
    source, tree = _module_tree()
    wiring = _wiring(source, tree)
    cards = {}
    for block in BLOCK_KIND:
        parts = [inspect.getsource(cls).rstrip() for cls in RULE_CLASSES.get(block, ())]
        parts += _constant_lines(source, tree, RULE_CONSTANTS.get(block, ()))
        if block in ("drain", "river_end"):
            parts.append("# no rule: a Sink takes what arrives")
        parts.append(wiring[block])
        cards[block] = "\n\n".join(parts)
    return cards


def page_payload() -> dict:
    """The game payload plus what the page needs from the module for the cards and the drawing."""
    payload = game_payload()
    payload.update(
        {
            "rule_source": rule_sources(),
            "analogy": dict(ANALOGY),
            "rule_name": dict(RULE_NAME),
            "kind_colour": dict(KIND_COLOUR),
            "layout": {k: list(v) for k, v in LAYOUT.items()},
        }
    )
    return payload


def logo_data_uri(logo_file: Path = LOGO_FILE, height: int = LOGO_HEIGHT_PX) -> str:
    """The logo, scaled down to the header's size and embedded as a PNG data URI."""
    from PIL import Image

    with Image.open(logo_file) as image:
        width = round(image.width * height / image.height)
        small = image.convert("RGBA").resize((width, height), Image.LANCZOS)
        buffer = io.BytesIO()
        small.save(buffer, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def build_blocks_game(
    source_dir: Path = SOURCE_DIR, output_file: Path = OUTPUT_FILE, logo_file: Path = LOGO_FILE
) -> Path:
    """Inline the stylesheet, the data, the script and the logo into one HTML file that works from file://."""
    page = (source_dir / "template.html").read_text(encoding="utf-8")
    parts = {
        "/*__STYLE__*/": (source_dir / "style.css").read_text(encoding="utf-8"),
        "/*__DATA__*/": _script_safe(json.dumps(page_payload(), separators=(",", ":"), ensure_ascii=False)),
        "/*__APP__*/": _script_safe((source_dir / "app.js").read_text(encoding="utf-8")),
        "@@LOGO@@": logo_data_uri(logo_file),
    }
    for placeholder, content in parts.items():
        if page.count(placeholder) != 1:
            raise ValueError(f"template must contain {placeholder} exactly once")
        page = page.replace(placeholder, content)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(page, encoding="utf-8")
    size = output_file.stat().st_size
    if size > PAGE_SIZE_BUDGET_BYTES:
        raise ValueError(f"page is {size // 1024} kB, over the {PAGE_SIZE_BUDGET_BYTES // 1024} kB budget")
    logger.info("wrote %s (%d kB)", output_file, size // 1024)
    return output_file


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    build_blocks_game()


if __name__ == "__main__":
    main()
