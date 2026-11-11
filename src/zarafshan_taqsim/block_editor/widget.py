"""The widget: the canvas in the browser on one side, TaqSim on the other.

    from zarafshan_taqsim.block_editor import BlockEditor
    BlockEditor(lang="en")          # Jupyter and Colab: the last line of a cell shows it
    mo.ui.anywidget(BlockEditor())  # marimo
"""

from __future__ import annotations

import json
from pathlib import Path

import anywidget
import traitlets

from zarafshan_taqsim.block_editor import lessons

_HERE = Path(__file__).parent


class BlockEditor(anywidget.AnyWidget):
    """Draw a TaqSim model with blocks; every change is run through TaqSim and the result sent back."""

    _esm = (_HERE / "editor.js").read_text(encoding="utf-8")
    _css = (_HERE / "editor.css").read_text(encoding="utf-8")

    lang = traitlets.Unicode("en").tag(sync=True)
    lesson = traitlets.Dict().tag(sync=True)  # texts, blocks and sliders of every step (Python → canvas)
    step = traitlets.Int(0).tag(sync=True)
    graph = traitlets.Dict().tag(sync=True)  # the drawing (canvas → Python)
    rev = traitlets.Int(0).tag(sync=True)  # counts the canvas's changes, so that it knows which answer is current
    request = traitlets.Unicode("").tag(sync=True)  # "solve": build this step's network for the learner
    state = traitlets.Dict().tag(sync=True)  # hints, scores, figures and code (Python → canvas)

    def __init__(self, lang: str = "en", lesson: str = "rationing", **kwargs) -> None:
        """`lesson` is "rationing" (the guided steps and the exercises) or "sandbox" (any network, no steps)."""
        super().__init__(lang=lang, graph={"nodes": [], "edges": []}, **kwargs)
        self._lesson = lesson
        self.lesson = lessons.lesson(self.lang, lesson)
        self._answered: tuple[str, dict] | None = None
        # The canvas raises `rev` with every change it sends. Hosts differ in the order they deliver the three
        # values, so each one is observed; `_changed` runs TaqSim only when the drawing or the step is new.
        self.observe(self._changed, names=["rev", "step", "graph"])
        self.observe(self._relabel, names=["lang"])
        self.observe(self._requested, names=["request"])
        self._changed()

    def _relabel(self, *_) -> None:
        self.lesson = lessons.lesson(self.lang, self._lesson)
        self._answered = None
        self._changed()

    def _requested(self, *_) -> None:
        if self.request.startswith("solve"):
            self.graph = lessons.solution(self.step, self.graph, self._lesson)
            self._changed()
        self.request = ""

    def _changed(self, *_) -> None:
        # Where a block sits on the canvas does not change the model
        drawing = {
            "nodes": [{key: node[key] for key in ("id", "kind", "params")} for node in self.graph.get("nodes", [])],
            "edges": self.graph.get("edges", []),
        }
        asked = json.dumps([drawing, self.step, self.lang], sort_keys=True)
        if self._answered is None or self._answered[0] != asked:
            try:
                state = lessons.evaluate(self.graph, self.step, self.lang, self._lesson)
            except Exception as error:  # never leave the learner with a silent canvas
                state = {"done": False, "messages": [{"level": "error", "text": str(error)}], "cards": [], "figures": [], "note": "", "code": ""}
            self._answered = (asked, state)
        self.state = {**self._answered[1], "rev": self.rev}
