"""The guided lesson of step 3 (rationing, notebook 02): what each step offers, asks for and shows.

`lesson(lang)` is the static part the canvas needs (texts, blocks, sliders). `evaluate(graph, step, lang)` is
the live part: it checks the drawing, runs it through TaqSim and returns scores, figures and the next hint.

One run of the model is always live. What needs hundreds of runs (the plan grids, the optimizer, the forecast
tables) is read from `precomputed.json`, made by `scripts/precompute_rationing.py` with the lesson's standard
numbers; the steps that use it therefore hold the reservoir and the farm at those numbers.
"""

from __future__ import annotations

import copy
import html
import io
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from taqsim.node.events import WaterSpilled

from zarafshan_taqsim import rationing_coursebook as rc
from zarafshan_taqsim.block_editor import compile as bc
from zarafshan_taqsim.block_editor import sandbox
from zarafshan_taqsim.block_editor.i18n import in_units, t

# The named blocks of the lesson. `id` is the name used in the Python code and stays English in every language.
BLOCKS: dict[str, dict] = {
    "river": {"kind": "Source", "params": {"regime": "central_asia", "seed": "72"}},
    "reservoir": {
        "kind": "Storage",
        "params": {
            "capacity": 40, "initial_storage": 20, "trigger": 0, "ration": 1.0, "optimise": False,
            "evaporation": 0.0, "winter_trigger": 0, "winter_ration": 1.0, "forecast": "none",
            "second_goal": "worst_month", "seasonal": False, "ration_late": 1.0, "caution": False, "late_forecast": False,
        },
    },  # fmt: skip
    "farm": {"kind": "Demand", "params": {"summer_need": 45, "winter_need": 5}},
    "winter_fields": {"kind": "Demand", "params": {"summer_need": 0, "winter_need": 15}},
    "downstream": {"kind": "Sink", "params": {}},
}
KIND_COLOUR = {"Source": "#0072B2", "Storage": "#CC79A7", "Demand": "#009E73", "Sink": "#595959"}
SUMMER_CAP = 2.0  # Mm³ a year: the summer shortage the forecast steps hold the farm to, as in the notebook
WORST_MONTH_GOAL = 45.0  # %: what the "many plans" step asks the learner's plan to stay within

_FARM = [
    {"key": "summer_need", "min": 20, "max": 70, "step": 5, "unit": "Mm³"},
    {"key": "winter_need", "min": 0, "max": 15, "step": 1, "unit": "Mm³"},
]
_SIZE = [
    {"key": "capacity", "min": 10, "max": 100, "step": 5, "unit": "Mm³"},
    {"key": "initial_storage", "min": 0, "max": 100, "step": 5, "unit": "Mm³", "max_from": "capacity"},
]
_SIZE_SHOWN = [{**field, "group": "size"} for field in _SIZE]  # under its own heading, below the rule
_RULE = [
    {"key": "trigger", "min": 0, "max": 100, "step": 1, "unit": "Mm³", "max_from": "capacity", "group": "rule"},
    {"key": "ration", "min": 0, "max": 1, "step": 0.05, "percent": True, "group": "rule"},
]
_OPTIMISE = [{"key": "optimise", "type": "toggle", "group": "rule"}]
_EVAPORATION = [{"key": "evaporation", "min": 0, "max": 0.06, "step": 0.01, "percent": True, "group": "loss"}]
_REGIME = [{"key": "regime", "type": "choice", "options": ["central_asia", "paper"]}]
_WINTER = [
    {"key": "winter_trigger", "min": 0, "max": 40, "step": 1, "unit": "Mm³", "group": "winter"},
    {"key": "winter_ration", "min": 0, "max": 1, "step": 0.05, "percent": True, "group": "winter"},
]
_WINTER_FAR = [{**_WINTER[0], "max": 120, "step": 2}, _WINTER[1]]
_FORECAST = [{"key": "forecast", "type": "choice", "options": ["none", "0.3", "0.5", "0.8", "1"], "group": "winter"}]

CHAIN_3 = (("river", "farm"), ("farm", "downstream"))
CHAIN_4 = (("river", "reservoir"), ("reservoir", "farm"), ("farm", "downstream"))
CHAIN_5 = (("river", "reservoir"), ("reservoir", "farm"), ("farm", "winter_fields"), ("winter_fields", "downstream"))
_FOUR = ["river", "reservoir", "farm", "downstream"]
_FIVE = ["river", "reservoir", "farm", "winter_fields", "downstream"]

# What a step holds fixed. The early steps have not met these settings yet; the later ones compare with tables
# that were computed for the standard reservoir, farm and river.
_NOT_YET = {"optimise": False, "evaporation": 0.0, "winter_trigger": 0, "winter_ration": 1.0, "forecast": "none"}
_STANDARD_SIZE = {"capacity": 40, "initial_storage": 20}
_STANDARD_FARM = {"summer_need": 45, "winter_need": 5}
_OUR_RIVER = {"regime": "central_asia"}
_CUT_DEEP = {"trigger": 16, "ration": 0.5}


def _locks(reservoir: dict, farm: dict | None = None) -> dict:
    return {"river": _OUR_RIVER, "reservoir": reservoir, "farm": farm or {}}


STEPS: list[dict] = [
    {"key": "river_farm", "palette": ["river", "farm", "downstream"], "target": CHAIN_3, "fields": {"farm": _FARM}, "locks": _locks(_NOT_YET)},
    {"key": "reservoir", "palette": _FOUR, "target": CHAIN_4, "fields": {"farm": _FARM, "reservoir": _SIZE}, "locks": _locks({**_NOT_YET, "trigger": 0, "ration": 1.0})},
    {"key": "rationing", "focus": "reservoir", "palette": _FOUR, "target": CHAIN_4, "fields": {"farm": _FARM, "reservoir": _SIZE + _RULE}, "locks": _locks(_NOT_YET)},
    {"key": "many_plans", "focus": "reservoir", "palette": _FOUR, "target": CHAIN_4, "fields": {"farm": _FARM, "reservoir": _RULE + _SIZE_SHOWN}, "locks": _locks({**_NOT_YET, **_STANDARD_SIZE}, _STANDARD_FARM)},
    {"key": "optimizer", "focus": "reservoir", "palette": _FOUR, "target": CHAIN_4, "fields": {"farm": _FARM, "reservoir": _RULE + _OPTIMISE + _SIZE_SHOWN}, "locks": _locks({**_NOT_YET, **_STANDARD_SIZE, "optimise": None}, _STANDARD_FARM)},
    {
        "key": "other_river",
        "focus": "reservoir",
        "palette": _FOUR,
        "target": CHAIN_4,
        "fields": {"river": _REGIME, "farm": _FARM, "reservoir": _RULE + _EVAPORATION + _SIZE_SHOWN},
        "locks": {"river": {}, "reservoir": {**_NOT_YET, **_STANDARD_SIZE, "evaporation": None}, "farm": _STANDARD_FARM},
    },
    {"key": "winter", "focus": "reservoir", "palette": _FIVE, "target": CHAIN_5, "fields": {"farm": _FARM, "reservoir": _WINTER + _RULE + _SIZE_SHOWN}, "locks": _locks({**_NOT_YET, **_STANDARD_SIZE, **_CUT_DEEP, "winter_trigger": None, "winter_ration": None}, _STANDARD_FARM)},
    {"key": "forecast", "focus": "reservoir", "palette": _FIVE, "target": CHAIN_5, "fields": {"farm": _FARM, "reservoir": _FORECAST + _WINTER_FAR + _RULE + _SIZE_SHOWN}, "locks": _locks({**_STANDARD_SIZE, **_CUT_DEEP, "optimise": False, "evaporation": 0.0}, _STANDARD_FARM)},
]  # fmt: skip
# The free sandbox is kept as a lesson of its own (`BlockEditor(lesson="sandbox")`), for use after the course
SANDBOX_STEPS: list[dict] = [{"key": "sandbox", "sandbox": True, "palette": list(sandbox.KINDS), "target": (), "fields": sandbox.FIELDS, "locks": {}}]
LESSONS: dict[str, list[dict]] = {"rationing": STEPS, "sandbox": SANDBOX_STEPS}  # the exercises join STEPS at the end of this file
# What the exercises add to the blocks is off in every step that does not say otherwise
_EXERCISES_OFF = {
    "river": {"seed": "72"},
    "reservoir": {"second_goal": "worst_month", "seasonal": False, "ration_late": 1.0, "caution": False, "late_forecast": False},
}


def locked(graph: dict, step: dict) -> dict:
    """The drawing with the step's fixed numbers put in place."""
    graph = copy.deepcopy(graph)
    for node in graph.get("nodes", []):
        node["params"] = {**BLOCKS.get(node["id"], {}).get("params", {}), **node.get("params", {}), **step["locks"].get(node["id"], {})}
    return graph


def solution(step: int, graph: dict | None = None, name: str = "rationing") -> dict:
    """The drawing a step asks for, keeping the numbers the learner already set."""
    spec = LESSONS[name][step]
    if spec.get("sandbox"):
        return sandbox.example()
    names = list(dict.fromkeys(name for edge in spec["target"] for name in edge))
    kept = {node["id"]: node.get("params", {}) for node in (graph or {}).get("nodes", [])}
    nodes = [{"id": name, "kind": BLOCKS[name]["kind"], "params": {**BLOCKS[name]["params"], **kept.get(name, {})}} for name in names]
    params = {node["id"]: node["params"] for node in nodes}
    # ... and the setting the step asks the learner to try
    if spec["key"] == "rationing" and not _rations(params["reservoir"]):
        params["reservoir"].update(trigger=min(16, float(params["reservoir"]["capacity"])), ration=0.5)
    elif spec["key"] == "many_plans":
        params["reservoir"].update(trigger=20, ration=0.55)
    elif spec["key"] == "optimizer":
        params["reservoir"].update(optimise=True)
    elif spec["key"] == "other_river":
        params["river"].update(regime="paper")
    elif spec["key"] == "winter":
        params["reservoir"].update(winter_trigger=24, winter_ration=0.0)
    elif spec["key"] == "forecast":
        params["reservoir"].update(forecast="1", winter_trigger=70, winter_ration=0.0)
    else:
        exercises.solve(spec["key"], params)
    return {"nodes": nodes, "edges": [{"source": a, "target": b} for a, b in spec["target"]]}


def lesson(lang: str, name: str = "rationing") -> dict:
    """Everything the canvas shows that does not depend on the drawing, in one language."""

    def worded(field: dict) -> dict:
        out = {**field, "label": t(lang, field.get("label_key", f"field.{field['key']}")), "help": t(lang, f"help.{field['key']}")}
        if "options" in field:
            out["options"] = [{"value": value, "label": t(lang, f"option.{field['key']}.{value}")} for value in field["options"]]
        return out

    steps = [
        {
            "title": t(lang, f"step.{step['key']}.title"),
            "body": t(lang, f"step.{step['key']}.body"),
            "task": t(lang, f"step.{step['key']}.task"),
            "palette": step["palette"],
            "sandbox": bool(step.get("sandbox")),
            "focus": step.get("focus", ""),
            "fields": {block: [worded(field) for field in fields] for block, fields in step["fields"].items()},
            "locks": step["locks"],
        }
        for step in LESSONS[name]
    ]
    blocks = {
        name: {
            "kind": block["kind"],
            "params": block["params"],
            "label": t(lang, f"block.{name}"),
            "about": t(lang, f"about.{name}"),
            "colour": KIND_COLOUR[block["kind"]],
        }
        for name, block in BLOCKS.items()
    }
    kinds = {
        kind: {"name": spec["name"], "colour": spec["colour"], "params": spec["params"], "about": t(lang, f"kind.{kind}")}
        for kind, spec in sandbox.KINDS.items()
    }
    ui_keys = (
        "blocks", "blocks_hint", "settings", "nothing_selected", "remove", "result", "next", "back", "show_me",
        "show_code", "hide_code", "working", "step_of", "done", "edge_selected", "no_settings", "start_over",
        "connect_hint", "code_about", "last_step", "fixed", "on", "off", "save", "load", "load_failed", "example",
        "group.size", "fixed_list",
        "group.rule", "group.loss", "group.winter", "group.goal",
    )  # fmt: skip
    languages = [{"code": "en", "name": "English"}, {"code": "ru", "name": "Русский"}, {"code": "uz", "name": "Oʻzbekcha"}]
    words = {"steps": steps, "blocks": blocks, "kinds": kinds, "ui": {key: t(lang, f"ui.{key}") for key in ui_keys}}
    return {**in_units(words, lang), "lang": lang, "languages": languages}


# --- The tables computed in advance -------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _tables() -> dict[str, pd.DataFrame]:
    stored = json.loads((Path(__file__).parent / "precomputed.json").read_text(encoding="utf-8"))
    return {name: pd.DataFrame(table["data"], columns=table["columns"]) for name, table in stored["tables"].items()}


def table(name: str) -> pd.DataFrame:
    return _tables()[name]


def beaten_by(mean_shortage: float, worst_month: float, grid: pd.DataFrame | None = None) -> int:
    """How many plans of a score table (the lesson's 441 grid plans unless another is given) are at least as good
    as this one on both scores and clearly better on one."""
    grid = table("grid") if grid is None else grid
    as_good = (grid["mean_shortage"] <= mean_shortage + 1e-6) & (grid["worst_month"] <= worst_month + 1e-6)
    better = (grid["mean_shortage"] < mean_shortage - 0.02) | (grid["worst_month"] < worst_month - 0.5)
    return int((as_good & better).sum())


# --- Running a drawing --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Run:
    result: rc.RunResult
    spilled: float | None  # Mm³ per year; None without a reservoir
    winter: rc.WinterScores | None  # with the winter fields in the chain
    params: dict  # the reservoir's settings ({} without one)


def _rations(params: dict) -> bool:
    return float(params.get("trigger", 0)) > 0 and float(params.get("ration", 1)) < 1


def _rations_in_winter(params: dict) -> bool:
    return float(params.get("winter_trigger", 0)) > 0 and float(params.get("winter_ration", 1)) < 1


def _settings_key() -> tuple:
    return (rc.CAPACITY_MM3, rc.START_STORAGE_MM3, rc.SUMMER_NEED_MM3, rc.WINTER_NEED_MM3, rc.YEARS, rc.SEED)


@lru_cache(maxsize=8)
def _inflows(years: int, seed: int, regime: rc.Regime) -> tuple[float, ...]:
    return rc.synthetic_inflows(years=years, seed=seed, regime=regime)


@lru_cache(maxsize=64)
def _reference(kind: str, key: tuple, regime: rc.Regime, evaporation: float = 0.0):
    """The runs the steps compare with: no reservoir, a reservoir that never rations, winter fields served in full."""
    inflows = _inflows(rc.YEARS, rc.SEED, regime)
    if kind == "none":
        return rc.simulate_without_reservoir(inflows)
    if kind == "winter_in_full":
        return rc.simulate_winter(inflows, rc.WINTER_IN_FULL)
    return rc.simulate_plan(inflows, rc.NO_RATIONING, evaporation_share=evaporation)


def run(graph: dict) -> Run:
    """Run the drawing through TaqSim and read off what the lesson looks at."""
    bc.configure_from(graph)
    regime = bc.regime_of(graph)
    inflows = _inflows(rc.YEARS, rc.SEED, regime)
    reservoir = next((node for node in graph["nodes"] if node["kind"] == "Storage"), None)
    params = reservoir["params"] if reservoir else {}
    winter = bc.has_winter_fields(graph)
    skill = bc.skill_of(params) if winter else None
    forecast = rc.seasonal_forecast(inflows, skill, regime=regime) if skill is not None else ()
    if params.get("caution"):
        forecast = tuple(CAUTION * value for value in forecast)
    system = bc.build(graph, inflows, forecast)
    system.simulate(len(inflows))
    shortage = rc.shortage_by_month(system)
    if reservoir is None:
        return Run(rc.RunResult(rc.NO_RATIONING, rc._scores(shortage), np.zeros(len(inflows)), shortage), None, None, {})
    plan = rc.Plan(trigger=min(float(params.get("trigger", 0)), rc.CAPACITY_MM3), ration=float(params.get("ration", 1)))
    spilled = sum(event.amount for event in system.nodes["reservoir"].events_of_type(WaterSpilled)) / rc.YEARS
    result = rc.RunResult(plan, rc._scores(shortage), rc._storage_path(system), shortage)
    return Run(result, spilled, rc._winter_scores(system) if winter else None, params)


# --- Figures ------------------------------------------------------------------------------------------------


def _svg(fig, tips: str = "") -> str:
    """The figure as SVG text; `tips` are extra SVG elements drawn on top (see `_tips`)."""
    buffer = io.StringIO()
    with mpl.rc_context({**rc._RC, "svg.fonttype": "none"}):
        fig.savefig(buffer, format="svg")
    plt.close(fig)
    text = buffer.getvalue()
    text = text[text.index("<svg") :]
    end = text.rindex("</svg>")
    return text[:end] + tips + text[end:]


def _tips(fig, points: list[tuple[float, float, str]], ax=None) -> str:
    """Invisible circles over points of the first chart; the canvas shows a point's text when it is pointed at.

    An SVG figure measures in points from its top left corner, so each point's place is taken from where
    matplotlib puts it in the figure (as a share of its width and height).
    """
    ax = ax or fig.axes[0]
    width, height = fig.get_figwidth() * 72.0, fig.get_figheight() * 72.0
    (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
    circles = []
    for x, y, text in points:
        if not (x0 <= x <= x1 and y0 <= y <= y1):
            continue
        fx, fy = fig.transFigure.inverted().transform(ax.transData.transform((x, y)))
        circles.append(f'<circle class="tq-tip" cx="{fx * width:.1f}" cy="{(1 - fy) * height:.1f}" r="6" data-tip="{html.escape(text, quote=True)}"/>')
    return f'<g>{"".join(circles)}</g>'


YOURS, IN_FULL, NO_RESERVOIR = rc.SHORTAGE, "#7a4fd0", "#1b8f5f"  # the marked points: the learner's plan, no rationing, no reservoir
CAUTION = 0.7  # exercise 5: the share of the forecast a cautious operator counts


def _year_tips(lang: str, fig, runs: dict[str, rc.RunResult], axes) -> str:
    """One invisible column per year over each bar chart; pointing at it tells that year's worst month for every run."""
    width, height = fig.get_figwidth() * 72.0, fig.get_figheight() * 72.0
    to_figure = fig.transFigure.inverted()
    years = len(next(iter(runs.values())).worst_month_by_year)
    texts = []
    for year in range(years):
        lines = [t(lang, "tip.year", year=year + 1)]
        for label, run in runs.items():
            value = float(run.worst_month_by_year[year])
            lines.append(t(lang, "tip.year_run", label=label, value=value) if value > 0.05 else t(lang, "tip.year_none", label=label))
        texts.append(html.escape("\n".join(lines), quote=True).replace("\n", "&#10;"))
    rects = []
    for ax in axes:
        low, high = ax.get_ylim()
        for year in range(years):
            (x0, y0), (x1, y1) = (to_figure.transform(ax.transData.transform(point)) for point in ((year + 0.5, low), (year + 1.5, high)))
            rects.append(f'<rect class="tq-tip tq-tip-bar" x="{x0 * width:.1f}" y="{(1 - y1) * height:.1f}" width="{(x1 - x0) * width:.2f}" height="{(y1 - y0) * height:.1f}" data-tip="{texts[year]}"/>')
    return f'<g>{"".join(rects)}</g>'


def _runs_svg(lang: str, fig, runs: dict[str, rc.RunResult]) -> str:
    """A `plot_runs` figure (bars on the left, storage on the right) with a text for every year of its bar charts."""
    return _svg(fig, _year_tips(lang, fig, runs, fig.axes[0::2]))


def _years_svg(lang: str, fig, runs: dict[str, rc.RunResult]) -> str:
    """A `plot_shortage_years` figure (one bar chart per run) with a text for every year."""
    return _svg(fig, _year_tips(lang, fig, runs, fig.axes))


def _mark(fig, x: float, y: float, label: str, colour: str = YOURS, offset: tuple[int, int] = (10, 10)):
    """Circle one point on a trade-off chart and write its name beside it, in the circle's colour."""
    ax = fig.axes[0]
    ax.scatter([x], [y], s=120, facecolors="none", edgecolors=colour, linewidths=2.4, zorder=6, clip_on=False)
    ax.annotate(
        label, (x, y), xytext=offset, textcoords="offset points", fontsize=9, color=colour, fontweight="bold", zorder=7,
        bbox={"boxstyle": "round,pad=0.2", "facecolor": "white", "edgecolor": "none", "alpha": 0.85},
    )  # fmt: skip
    return fig


def _tradeoff(
    lang: str,
    mine: rc.RunResult,
    in_full: rc.RunResult,
    found: pd.DataFrame | None = None,
    grid: pd.DataFrame | None = None,
    without: rc.RunResult | None = None,
    found_tip: str = "tip.plan",
):
    """All plans of a grid as dots, with the learner's plan and the plan without rationing circled in two colours,
    and the system without a reservoir as a square."""
    grid = table("grid") if grid is None else grid
    fig = rc.plot_tradeoff(grid, found=found)
    for text in list(fig.axes[0].texts):
        if "lie further right" in text.get_text():  # true, but it reads like something the learner should act on
            text.remove()
    _mark(fig, in_full.scores.mean_shortage, in_full.scores.worst_month, t(lang, "label.in_full"), IN_FULL, (10, 12))
    _mark(fig, mine.scores.mean_shortage, mine.scores.worst_month, t(lang, "label.yours"), YOURS, (12, -16))
    # Pointing at an unbeaten dot (and, with the optimizer, at one of its dots) tells which trigger and ration it is
    points = _plan_points(lang, rc.front_of(grid)) + (_plan_points(lang, found, key=found_tip) if found is not None else [])
    if without is not None and without.scores.mean_shortage <= rc.MEAN_SHORTAGE_AXIS_MAX:
        x, y = without.scores.mean_shortage, without.scores.worst_month
        fig.axes[0].scatter([x], [y], s=70, marker="s", color=NO_RESERVOIR, edgecolors=rc.SURFACE, linewidths=1.0, zorder=5)
        fig.axes[0].annotate(
            t(lang, "label.without_reservoir"), (x, y), xytext=(0, 10), textcoords="offset points", ha="center", fontsize=9, color=NO_RESERVOIR, fontweight="bold",
            bbox={"boxstyle": "round,pad=0.2", "facecolor": "white", "edgecolor": "none", "alpha": 0.85},
        )  # fmt: skip
        points.append((x, y, t(lang, "tip.without_reservoir", missed=x, worst=y)))
    return _svg(fig, _tips(fig, points))


def _plan_points(lang: str, plans: pd.DataFrame, label: str = "", key: str = "tip.plan") -> list[tuple[float, float, str]]:
    """For each plan of a score table: where its dot is, and the text that says which trigger and ration it is."""
    return [
        (
            row.mean_shortage,
            row.worst_month,
            (f"{label}: " if label else "") + t(lang, key, trigger=row.trigger, ration=row.ration * 100, late=getattr(row, "ration_late", row.ration) * 100, missed=row.mean_shortage, worst=row.worst_month),
        )
        for row in plans.itertuples()
    ]


def _figure(fig_or_svg, caption: str) -> dict:
    """A figure with the words that explain it, shown right above it."""
    return {"svg": fig_or_svg if isinstance(fig_or_svg, str) else _svg(fig_or_svg), "caption": caption}  # in_units leaves "svg" alone


def _goal_cards(lang: str, mine: Run, in_full: rc.RunResult, second: str = "worst_month") -> list[dict]:
    """The three scores, saying which two are the goals and which one is only there to look at."""
    cards = _score_cards(lang, mine, in_full, t(lang, "label.in_full_short"))[:3]
    goal, info = (1, 2) if second == "worst_month" else (2, 1)  # which of the last two cards is the second goal
    cards[0]["tag"], cards[goal]["tag"], cards[info]["tag"] = t(lang, "tag.goal", n=1), t(lang, "tag.goal", n=2), t(lang, "tag.info")
    cards[info]["quiet"] = True
    return cards


def _plan_story(lang: str, mine: Run, in_full: rc.RunResult) -> str:
    """In plain words, what the learner's plan did over the hundred years."""
    dry_before = int((in_full.shortage_by_month > 0.5).sum())
    if not _rations(mine.params):
        return t(lang, "note.story_no_rationing", dry_before=dry_before)
    plan, shortage = mine.result.plan, mine.result.shortage_by_month
    cut = (1.0 - plan.ration) * 100.0
    dry_months = int((shortage > cut + 0.5).sum())
    dry = t(lang, "note.story_dry", dry_months=dry_months) if dry_months else t(lang, "note.story_never_dry")
    return t(
        lang,
        "note.story",
        trigger=plan.trigger,
        ration=plan.ration * 100,
        cut=cut,
        short_months=int((shortage > 0.5).sum()),
        dry=dry,
        dry_before=dry_before,
        months=len(shortage),
    )


@lru_cache(maxsize=16)
def _fixed_figure(name: str, lang: str) -> str:
    """The figures that do not depend on the learner's settings; drawn once."""
    ours = _inflows(rc.YEARS, rc.SEED, rc.CENTRAL_ASIA_REGIME)
    if name == "score_maps":
        return _svg(rc.plot_score_maps(table("grid")))
    if name == "regimes":
        paper = _inflows(rc.YEARS, rc.SEED, rc.PAPER_REGIME)
        cases = {t(lang, "label.our_river"): (ours, table("grid")), t(lang, "label.paper_river"): (paper, table("paper_grid"))}
        fig = rc.plot_regime_comparison(cases)
        points = [point for label, (_, plans) in cases.items() for point in _plan_points(lang, rc.front_of(plans), label)]
        return _svg(fig, _tips(fig, points, fig.axes[1]))
    if name == "evaporation":
        fronts = {t(lang, "label.no_evaporation"): table("grid"), t(lang, "label.evaporation"): table("evaporation_grid")}
        fig = rc.plot_front_shift(fronts)
        points = [point for label, plans in fronts.items() for point in _plan_points(lang, rc.front_of(plans), label)]
        return _svg(fig, _tips(fig, points))
    raise KeyError(name)


def _winter_fronts(lang: str, with_forecasts: bool) -> dict[str, pd.DataFrame]:
    alone = {t(lang, "label.storage_alone"): table("storage_only")}
    if not with_forecasts:
        return alone
    return {
        t(lang, "label.perfect_forecast"): table("skill_1"),
        t(lang, "label.forecast_skill", skill=0.8): table("skill_0.8"),
        t(lang, "label.forecast_skill", skill=0.5): table("skill_0.5"),
        **alone,
    }


def _found_table(lang: str) -> dict:
    """A handful of the optimizer's plans, from least water missed to mildest worst month."""
    front = rc.front_of(table("found"))
    front = front[front["mean_shortage"] <= rc.MEAN_SHORTAGE_AXIS_MAX]
    rows = front.iloc[np.unique(np.linspace(0, len(front) - 1, 6).round().astype(int))]
    return {
        "columns": [t(lang, key) for key in ("field.trigger", "field.ration", "card.mean_shortage", "card.worst_month")],
        "rows": [[f"{row.trigger:.1f} Mm³", f"{row.ration * 100:.0f} %", f"{row.mean_shortage:.2f} Mm³", f"{row.worst_month:.0f} %"] for row in rows.itertuples()],
    }


# --- What each step shows -----------------------------------------------------------------------------------


def _card(lang: str, key: str, value: str, other: str = "", other_name: str = "") -> dict:
    return {"label": t(lang, f"card.{key}"), "value": value, "sub": f"{other_name}: {other}" if other else ""}


def _score_cards(lang: str, mine: Run, other: rc.RunResult | None, other_name: str) -> list[dict]:
    a, b = mine.result.scores, other.scores if other else None
    cards = [
        _card(lang, "mean_shortage", f"{a.mean_shortage:.1f} Mm³", f"{b.mean_shortage:.1f}" if b else "", other_name),
        _card(lang, "worst_month", f"{a.worst_month:.0f} %", f"{b.worst_month:.0f} %" if b else "", other_name),
        _card(lang, "years_short", t(lang, "card.of_years", n=a.years_short, years=rc.YEARS), str(b.years_short) if b else "", other_name),
    ]
    if mine.spilled is not None:
        cards.append(_card(lang, "spilled", f"{mine.spilled:.1f} Mm³"))
    return cards


def _plan_label(lang: str, plan: rc.Plan) -> str:
    return f"{t(lang, 'label.yours')}: {t(lang, 'label.plan', trigger=plan.trigger, ration=plan.ration * 100)}"


def _show_basic(state: dict, mine: Run, lang: str, graph: dict, reservoir_step: bool = False) -> None:
    """One run against its reference: what steps 1 to 3 show, and what later steps show until their own part is built."""
    key, regime, evaporation = _settings_key(), bc.regime_of(graph), float(mine.params.get("evaporation", 0.0))
    scores = mine.result.scores
    if mine.spilled is None:
        alone = {t(lang, "label.no_reservoir"): mine.result}
        state["figures"] = [_years_svg(lang, rc.plot_shortage_years(alone), alone)]
        state["cards"] = _score_cards(lang, mine, None, "")
        state["note"] = t(lang, "note.river_farm", need=rc.YEARLY_NEED_MM3, missed=scores.mean_shortage, short=scores.years_short, years=rc.YEARS, summer=rc.SUMMER_NEED_MM3)  # fmt: skip
    elif not _rations(mine.params):
        without = _reference("none", key, regime)
        runs = {t(lang, "label.no_reservoir"): without, t(lang, "label.with_reservoir", capacity=rc.CAPACITY_MM3): mine.result}
        if reservoir_step:
            state["figures"] = [_years_svg(lang, rc.plot_shortage_years(runs), runs)]
        else:
            only = {t(lang, "label.in_full"): mine.result}
            state["figures"] = [_runs_svg(lang, rc.plot_runs(only, first_year=rc.drought_window_start(mine.result)), only)]
        state["cards"] = _score_cards(lang, mine, without, t(lang, "label.before"))
        state["note"] = t(lang, "note.reservoir", capacity=rc.CAPACITY_MM3, a_short=without.scores.years_short, b_short=scores.years_short, a_missed=without.scores.mean_shortage, b_missed=scores.mean_shortage, spilled=mine.spilled, worst=scores.worst_month)  # fmt: skip
    else:
        in_full = _reference("full", key, regime, evaporation)
        runs = {t(lang, "label.in_full"): in_full, _plan_label(lang, mine.result.plan): mine.result}
        state["figures"] = [_runs_svg(lang, rc.plot_runs(runs, first_year=rc.drought_window_start(in_full)), runs)]
        state["cards"] = _score_cards(lang, mine, in_full, t(lang, "label.in_full_short"))
        state["note"] = t(lang, "note.rationing", lowest=float(mine.result.storage.min()), a_worst=in_full.scores.worst_month, b_worst=scores.worst_month, a_missed=in_full.scores.mean_shortage, b_missed=scores.mean_shortage)  # fmt: skip


def _show_many_plans(state: dict, mine: Run, lang: str, graph: dict) -> str | None:
    scores = mine.result.scores
    beaten = beaten_by(scores.mean_shortage, scores.worst_month)
    in_full = _reference("full", _settings_key(), rc.CENTRAL_ASIA_REGIME)
    without = _reference("none", _settings_key(), rc.CENTRAL_ASIA_REGIME)
    runs = {t(lang, "label.in_full"): in_full, _plan_label(lang, mine.result.plan): mine.result}
    state["figures"] = [
        _figure(_tradeoff(lang, mine.result, in_full, without=without), t(lang, "caption.tradeoff")),
        _figure(_fixed_figure("score_maps", lang), t(lang, "caption.score_maps")),
        _figure(_runs_svg(lang, rc.plot_runs(runs, first_year=rc.drought_window_start(in_full)), runs), t(lang, "caption.plan_run")),
    ]
    state["cards"] = _goal_cards(lang, mine, in_full)
    verdict = t(lang, "note.unbeaten") if beaten == 0 else t(lang, "note.beaten", n=beaten)
    state["note"] = _plan_story(lang, mine, in_full) + " " + verdict
    if not _rations(mine.params):
        return "hint.set_rule"
    if beaten or scores.worst_month > WORST_MONTH_GOAL + 0.5:
        return "hint.many_plans_goal"
    return None


def _show_optimizer(state: dict, mine: Run, lang: str, graph: dict) -> str | None:
    in_full = _reference("full", _settings_key(), rc.CENTRAL_ASIA_REGIME)
    state["cards"] = _goal_cards(lang, mine, in_full)
    without = _reference("none", _settings_key(), rc.CENTRAL_ASIA_REGIME)
    if not mine.params.get("optimise"):
        state["figures"] = [_figure(_tradeoff(lang, mine.result, in_full, without=without), t(lang, "caption.optimizer_off"))]
        state["note"] = ""
        return "hint.optimizer"
    found = table("found")
    state["figures"] = [_figure(_tradeoff(lang, mine.result, in_full, found=found, without=without), t(lang, "caption.optimizer"))]
    state["table"] = _found_table(lang)
    state["note"] = t(lang, "note.optimizer", n=len(found), distinct=len(rc.front_of(found)))
    return None


@lru_cache(maxsize=64)
def _on_standard_system(trigger: float, ration: float, key: tuple) -> rc.RunResult:
    """The same plan on the course's own system: the summer-peak river, no evaporation."""
    return rc.simulate_plan(_inflows(rc.YEARS, rc.SEED, rc.CENTRAL_ASIA_REGIME), rc.Plan(trigger, ration))


def _show_other_river(state: dict, mine: Run, lang: str, graph: dict) -> str | None:
    """One plan on a changed system: another river, evaporation from the reservoir, or both."""
    regime, evaporation = bc.regime_of(graph), float(mine.params.get("evaporation", 0.0))
    paper, plan, key = regime.name == "paper", mine.result.plan, _settings_key()
    river = t(lang, "system.winter" if paper else "system.summer")
    system = t(lang, "system.evaporation", river=river, share=evaporation * 100) if evaporation > 0 else t(lang, "system.no_evaporation", river=river)
    changed = paper or evaporation > 0

    # Figure 1: the run itself, with the system named in every title
    in_full = _reference("full", key, regime, evaporation)
    runs = {f"{t(lang, 'label.in_full')} · {system}": in_full}
    if _rations(mine.params):
        runs[f"{_plan_label(lang, plan)} · {system}"] = mine.result
    caption = t(lang, "caption.system_run" if _rations(mine.params) else "caption.system_run_full", system=system)
    state["figures"] = [_figure(_runs_svg(lang, rc.plot_runs(runs, first_year=rc.drought_window_start(in_full)), runs), caption)]
    if paper:
        state["figures"].append(_figure(_fixed_figure("regimes", lang), t(lang, "caption.regimes")))
    if evaporation > 0:
        state["figures"].append(_figure(_fixed_figure("evaporation", lang), t(lang, "caption.evaporation_shift")))

    # The cards compare the same plan on the system before the change: the plan is the same, the system is not
    if changed:
        before = _on_standard_system(plan.trigger, plan.ration, key)
        state["cards"] = _score_cards(lang, mine, before, t(lang, "label.standard_system"))
        state["note"] = t(lang, "note.system_changed", plan=t(lang, "label.plan", trigger=plan.trigger, ration=plan.ration * 100), system=system)
        state["ok_text"] = t(lang, "ok.other_river", system=system)
    else:
        state["cards"] = _score_cards(lang, mine, in_full, t(lang, "label.in_full_short"))
        state["note"] = t(lang, "note.system_same", system=system)
    return None if changed else "hint.other_river"


@rc._styled
def plot_forecast_bars(losses: dict[str, float], chosen: str | None, cap: float):
    """What the winter fields give up for each quality of forecast, with the learner's choice in another colour."""
    fig, ax = plt.subplots(figsize=(7.4, 3.5))
    names, heights = list(losses), list(losses.values())
    bars = ax.bar(names, heights, width=0.62, color=[YOURS if name == chosen else rc.WATER for name in names])
    for bar, value in zip(bars, heights, strict=True):
        ax.text(bar.get_x() + bar.get_width() / 2, value + max(heights) * 0.02, f"{value:.1f}", ha="center", fontsize=9.5, color=rc.INK, fontweight="bold")
    ax.set_title(f"What the winter fields give up when the farm misses at most {cap:g} Mm³ a year", loc="left")
    ax.set_ylabel("Winter fields: water missed\n(Mm³ per year)")
    ax.set_xlabel("Quality of the forecast (skill: 0 = knows nothing, 1 = perfect)")
    ax.set_ylim(0, max(heights) * 1.18)
    rc._style(ax)
    fig.tight_layout()
    return fig


_SKILL_NAMES = {None: "no forecast", 0.3: "0.3", 0.5: "0.5", 0.65: "0.65", 0.8: "0.8", 0.9: "0.9", 1.0: "1.0 (perfect)"}


def _forecast_losses() -> dict[float | None, float]:
    """The least the winter fields can lose while the farm stays within the cap, without and with each forecast."""
    losses = {None: rc.least_winter_shortage(table("storage_only"), SUMMER_CAP)}
    for skill in (0.3, 0.5, 0.65, 0.8, 0.9, 1.0):
        losses[skill] = rc.least_winter_shortage(table(f"skill_{skill:g}"), SUMMER_CAP)
    return losses


def _show_winter(state: dict, mine: Run, lang: str, graph: dict, with_forecasts: bool = False) -> str | None:
    scores, full = mine.winter, _reference("winter_in_full", _settings_key(), rc.CENTRAL_ASIA_REGIME).scores
    name = t(lang, "label.winter_in_full")
    state["cards"] = [
        _card(lang, "summer_shortage", f"{scores.summer_shortage:.1f} Mm³", f"{full.summer_shortage:.1f}", name),
        _card(lang, "winter_shortage", f"{scores.winter_shortage:.1f} Mm³", f"{full.winter_shortage:.1f}", name),
        _card(lang, "worst_month", f"{scores.worst_month:.0f} %", f"{full.worst_month:.0f} %", name),
    ]
    curves = _winter_fronts(lang, with_forecasts)
    fronts = _mark(rc.plot_winter_fronts(curves), scores.summer_shortage, scores.winter_shortage, t(lang, "label.yours"))
    points = [
        (row.summer_shortage, row.winter_shortage, f"{label}: " + t(lang, "tip.winter_plan", trigger=row.winter_trigger, ration=row.winter_ration * 100, summer=row.summer_shortage, winter=row.winter_shortage))
        for label, frame in curves.items()
        for row in rc.winter_front_of(frame).itertuples()
    ]
    fronts = _svg(fronts, _tips(fronts, points))
    gain, price = full.summer_shortage - scores.summer_shortage, scores.winter_shortage - full.winter_shortage
    if not with_forecasts:
        state["figures"] = [fronts]
        state["note"] = t(lang, "note.winter", total=rc.WINTER_FIELDS_TOTAL_MM3, gain=gain, price=price)
        return None if _rations_in_winter(mine.params) else "hint.winter_rule"
    skill = bc.skill_of(mine.params)
    losses = _forecast_losses()
    bars = plot_forecast_bars({_SKILL_NAMES[key]: value for key, value in losses.items()}, _SKILL_NAMES.get(skill), SUMMER_CAP)
    value_caption = t(lang, "caption.forecast_value", cap=SUMMER_CAP, none=losses[None], mid=losses[0.5], perfect=losses[1.0], gain=losses[None] - losses[1.0], small=losses[None] - losses[0.5])
    state["figures"] = [_figure(fronts, t(lang, "caption.forecast_fronts")), _figure(bars, value_caption)]
    state["note"] = t(lang, "note.forecast_off") if skill is None else t(lang, "note.forecast", skill=skill)
    return "hint.forecast" if skill is None else None


_SHOW = {
    "many_plans": _show_many_plans,
    "optimizer": _show_optimizer,
    "other_river": _show_other_river,
    "winter": _show_winter,
    "forecast": lambda state, mine, lang, graph: _show_winter(state, mine, lang, graph, with_forecasts=True),
}


def evaluate(graph: dict, step_index: int, lang: str, name: str = "rationing") -> dict:
    """Check the drawing against the step, run it if it can run, and say what to do next."""
    return in_units(_evaluate(graph, step_index, lang, LESSONS[name]), lang)


def _evaluate(graph: dict, step_index: int, lang: str, steps: list[dict]) -> dict:
    step = steps[max(0, min(step_index, len(steps) - 1))]
    if step.get("sandbox"):
        return sandbox.evaluate(graph, lang, lambda fig, runs=None: _years_svg(lang, fig, runs) if runs else _svg(fig))
    graph = locked(graph, step)
    names = {name: t(lang, f"block.{name}") for name in BLOCKS}
    state: dict = {"done": False, "messages": [], "cards": [], "figures": [], "note": "", "code": "", "table": None}

    def todo(key: str, **blanks) -> None:
        state["messages"].append({"level": "todo", "text": t(lang, key, **blanks)})

    present = [node["id"] for node in graph.get("nodes", [])]
    wanted = list(dict.fromkeys(name for edge in step["target"] for name in edge))
    extra = [name for name in present if name not in wanted]
    missing = [name for name in wanted if name not in present]
    if extra:
        todo("hint.remove_block", block=names.get(extra[0], extra[0]))
        return state
    if missing:
        todo("hint.add_block", block=names[missing[0]])
    problems = bc.check(graph)
    if not missing:
        for problem in problems[:2]:
            todo(f"problem.{problem.key}", **({"block": names.get(problem.names[0], problem.names[0])} if problem.names else {}))
    if problems:
        return state

    try:
        mine = run(graph)
    except Exception as error:  # TaqSim's own message is better than none
        state["messages"].append({"level": "error", "text": t(lang, "problem.taqsim", error=str(error))})
        return state
    state["code"] = bc.to_python(graph)

    built = {(edge["source"], edge["target"]) for edge in graph["edges"]} == set(step["target"]) and not missing
    if built and step["key"] in _SHOW:
        hint = _SHOW[step["key"]](state, mine, lang, graph)
    else:
        _show_basic(state, mine, lang, graph, reservoir_step=step["key"] == "reservoir")
        hint = "hint.set_rule" if step["key"] == "rationing" and not _rations(mine.params) else None
    if not built:
        todo(f"hint.{step['key']}")
    elif hint:
        todo(hint, goal=WORST_MONTH_GOAL)
    else:
        state["done"] = True
        state["messages"].append({"level": "ok", "text": state.get("ok_text") or t(lang, f"step.{step['key']}.done")})
    state.pop("ok_text", None)
    return state


# --- The exercises join the lesson ---------------------------------------------------------------------------
from zarafshan_taqsim.block_editor import exercises  # noqa: E402  (it uses the helpers above)

STEPS.extend(exercises.STEPS)
_SHOW.update(exercises.SHOW)
for _step in STEPS:
    for _block, _off in _EXERCISES_OFF.items():
        _step["locks"][_block] = {**_off, **_step["locks"].get(_block, {})}
    # a lock of None means: free in this step
    _step["locks"] = {block: {k: v for k, v in keys.items() if v is not None} for block, keys in _step["locks"].items()}
