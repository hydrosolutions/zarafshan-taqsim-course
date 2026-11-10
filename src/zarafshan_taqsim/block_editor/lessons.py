"""The guided lesson of step 2 (rationing): what each step offers, asks for and shows.

`lesson(lang)` is the static part the canvas needs (texts, blocks, sliders). `evaluate(graph, step, lang)` is
the live part: it checks the drawing, runs it through TaqSim and returns scores, figures and the next hint.
"""

from __future__ import annotations

import io
from functools import lru_cache

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from taqsim.node.events import WaterSpilled

from zarafshan_taqsim import rationing_coursebook as rc
from zarafshan_taqsim.block_editor import compile as bc
from zarafshan_taqsim.block_editor.i18n import t

# The named blocks of the lesson. `id` is the name used in the Python code and stays English in every language.
BLOCKS: dict[str, dict] = {
    "river": {"kind": "Source", "params": {}},
    "reservoir": {"kind": "Storage", "params": {"capacity": 40, "initial_storage": 20, "trigger": 0, "ration": 1.0}},
    "farm": {"kind": "Demand", "params": {"summer_need": 45, "winter_need": 5}},
    "downstream": {"kind": "Sink", "params": {}},
}
KIND_COLOUR = {"Source": "#0072B2", "Storage": "#CC79A7", "Demand": "#009E73", "Sink": "#595959"}

_FARM_FIELDS = [
    {"key": "summer_need", "min": 20, "max": 70, "step": 5, "unit": "Mm³"},
    {"key": "winter_need", "min": 0, "max": 15, "step": 1, "unit": "Mm³"},
]
_SIZE_FIELDS = [
    {"key": "capacity", "min": 10, "max": 100, "step": 5, "unit": "Mm³"},
    {"key": "initial_storage", "min": 0, "max": 100, "step": 5, "unit": "Mm³", "max_from": "capacity"},
]
_RULE_FIELDS = [
    {"key": "trigger", "min": 0, "max": 100, "step": 1, "unit": "Mm³", "max_from": "capacity", "group": "rule"},
    {"key": "ration", "min": 0, "max": 1, "step": 0.05, "percent": True, "group": "rule"},
]

CHAIN_3 = (("river", "farm"), ("farm", "downstream"))
CHAIN_4 = (("river", "reservoir"), ("reservoir", "farm"), ("farm", "downstream"))

STEPS: list[dict] = [
    {"key": "river_farm", "palette": ["river", "farm", "downstream"], "target": CHAIN_3, "fields": {"farm": _FARM_FIELDS}},
    {
        "key": "reservoir",
        "palette": ["river", "reservoir", "farm", "downstream"],
        "target": CHAIN_4,
        "fields": {"farm": _FARM_FIELDS, "reservoir": _SIZE_FIELDS},
    },
    {
        "key": "rationing",
        "palette": ["river", "reservoir", "farm", "downstream"],
        "target": CHAIN_4,
        "fields": {"farm": _FARM_FIELDS, "reservoir": _SIZE_FIELDS + _RULE_FIELDS},
    },
]

_POSITIONS = {
    3: {"river": (20, 60), "farm": (250, 60), "downstream": (480, 60)},
    4: {"river": (20, 60), "reservoir": (170, 60), "farm": (320, 60), "downstream": (470, 60)},
}


def solution(step: int, graph: dict | None = None) -> dict:
    """The drawing a step asks for, keeping the numbers the learner already set."""
    target = STEPS[step]["target"]
    names = list(dict.fromkeys(name for edge in target for name in edge))
    kept = {node["id"]: node.get("params", {}) for node in (graph or {}).get("nodes", [])}
    nodes = []
    for name in names:
        x, y = _POSITIONS[len(names)][name]
        params = {**BLOCKS[name]["params"], **kept.get(name, {})}
        nodes.append({"id": name, "kind": BLOCKS[name]["kind"], "x": x, "y": y, "params": params})
    if STEPS[step]["key"] == "rationing":
        reservoir = next(node for node in nodes if node["id"] == "reservoir")
        if not _rations(reservoir["params"]):
            reservoir["params"].update(trigger=min(16, reservoir["params"]["capacity"]), ration=0.5)
    return {"nodes": nodes, "edges": [{"source": a, "target": b} for a, b in target]}


def lesson(lang: str) -> dict:
    """Everything the canvas shows that does not depend on the drawing, in one language."""
    steps = []
    for index, step in enumerate(STEPS):
        fields = {
            block: [{**field, "label": t(lang, f"field.{field['key']}"), "help": t(lang, f"help.{field['key']}")} for field in block_fields]
            for block, block_fields in step["fields"].items()
        }
        steps.append(
            {
                "title": t(lang, f"step.{step['key']}.title"),
                "body": t(lang, f"step.{step['key']}.body"),
                "task": t(lang, f"step.{step['key']}.task"),
                "palette": step["palette"],
                "fields": fields,
                "number": index + 1,
            }
        )
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
    ui_keys = (
        "blocks", "blocks_hint", "settings", "nothing_selected", "remove", "result", "next", "back", "show_me",
        "show_code", "hide_code", "working", "step_of", "done", "edge_selected", "no_settings", "start_over",
        "rule", "connect_hint", "code_about", "last_step",
    )  # fmt: skip
    return {"steps": steps, "blocks": blocks, "ui": {key: t(lang, f"ui.{key}") for key in ui_keys}}


# --- Running a drawing --------------------------------------------------------------------------------------


def _rations(params: dict) -> bool:
    return float(params.get("trigger", 0)) > 0 and float(params.get("ration", 1)) < 1


def _settings_key() -> tuple:
    return (rc.CAPACITY_MM3, rc.START_STORAGE_MM3, rc.SUMMER_NEED_MM3, rc.WINTER_NEED_MM3, rc.YEARS, rc.SEED)


@lru_cache(maxsize=4)
def _inflows(years: int, seed: int) -> tuple[float, ...]:
    return rc.synthetic_inflows(years=years, seed=seed)


@lru_cache(maxsize=32)
def _reference(kind: str, key: tuple) -> rc.RunResult:
    """The two runs every step compares with: no reservoir, and a reservoir that never rations."""
    inflows = _inflows(rc.YEARS, rc.SEED)
    return rc.simulate_without_reservoir(inflows) if kind == "none" else rc.simulate_plan(inflows, rc.NO_RATIONING)


def run(graph: dict) -> tuple[rc.RunResult, float | None]:
    """Run the drawing through TaqSim. Returns the run and, with a reservoir, the spill in Mm³ per year."""
    bc.configure_from(graph)
    inflows = _inflows(rc.YEARS, rc.SEED)
    system = bc.build(graph, inflows)
    system.simulate(len(inflows))
    shortage = rc.shortage_by_month(system)
    reservoir = next((node for node in graph["nodes"] if node["kind"] == "Storage"), None)
    if reservoir is None:
        return rc.RunResult(rc.NO_RATIONING, rc._scores(shortage), np.zeros(len(inflows)), shortage), None
    params = reservoir["params"]
    plan = rc.Plan(trigger=min(float(params.get("trigger", 0)), rc.CAPACITY_MM3), ration=float(params.get("ration", 1)))
    spilled = sum(event.amount for event in system.nodes["reservoir"].events_of_type(WaterSpilled)) / rc.YEARS
    return rc.RunResult(plan, rc._scores(shortage), rc._storage_path(system), shortage), spilled


def _svg(fig) -> str:
    buffer = io.StringIO()
    with mpl.rc_context({**rc._RC, "svg.fonttype": "none"}):
        fig.savefig(buffer, format="svg")
    plt.close(fig)
    text = buffer.getvalue()
    return text[text.index("<svg") :]


def _cards(lang: str, mine: rc.RunResult, other: rc.RunResult | None, other_name: str, spilled: float | None) -> list[dict]:
    def card(key: str, value: str, before: str | None) -> dict:
        return {"label": t(lang, f"card.{key}"), "value": value, "sub": f"{other_name}: {before}" if before else ""}

    a, b = mine.scores, other.scores if other else None
    cards = [
        card("mean_shortage", f"{a.mean_shortage:.1f} Mm³", f"{b.mean_shortage:.1f}" if b else None),
        card("worst_month", f"{a.worst_month:.0f} %", f"{b.worst_month:.0f} %" if b else None),
        card("years_short", t(lang, "card.of_years", n=a.years_short, years=rc.YEARS), str(b.years_short) if b else None),
    ]
    if spilled is not None:
        cards.append(card("spilled", f"{spilled:.1f} Mm³", None))
    return cards


def _missing(graph: dict, step: dict) -> list[str]:
    present = {node["id"] for node in graph.get("nodes", [])}
    wanted = dict.fromkeys(name for edge in step["target"] for name in edge)
    return [name for name in wanted if name not in present]


def evaluate(graph: dict, step_index: int, lang: str) -> dict:
    """Check the drawing against the step, run it if it can run, and say what to do next."""
    step = STEPS[max(0, min(step_index, len(STEPS) - 1))]
    names = {name: t(lang, f"block.{name}") for name in BLOCKS}
    state: dict = {"done": False, "messages": [], "cards": [], "figures": [], "note": "", "code": ""}

    def todo(key: str, **blanks) -> None:
        state["messages"].append({"level": "todo", "text": t(lang, key, **blanks)})

    missing = _missing(graph, step)
    if missing:
        todo("hint.add_block", block=names[missing[0]])
    problems = bc.check(graph)
    if not missing:
        for problem in problems[:2]:
            blanks = {"block": names.get(problem.names[0], problem.names[0])} if problem.names else {}
            todo(f"problem.{problem.key}", **blanks)
    if problems:
        return state

    try:
        mine, spilled = run(graph)
    except Exception as error:  # TaqSim's own message is better than none
        state["messages"].append({"level": "error", "text": t(lang, "problem.taqsim", error=str(error))})
        return state
    state["code"] = bc.to_python(graph)

    edges = {(edge["source"], edge["target"]) for edge in graph["edges"]}
    built = edges == set(step["target"]) and not missing
    has_reservoir = spilled is not None
    key = _settings_key()
    without = _reference("none", key)
    yours = t(lang, "label.yours")
    if not has_reservoir:
        label = t(lang, "label.no_reservoir")
        state["figures"] = [_svg(rc.plot_shortage_years({label: mine}))]
        state["cards"] = _cards(lang, mine, None, "", None)
        state["note"] = t(lang, "note.river_farm", need=rc.YEARLY_NEED_MM3, missed=mine.scores.mean_shortage, short=mine.scores.years_short, years=rc.YEARS, summer=rc.SUMMER_NEED_MM3)  # fmt: skip
    elif step["key"] == "reservoir" or not _rations(mine.plan.__dict__):
        runs = {t(lang, "label.no_reservoir"): without, t(lang, "label.with_reservoir", capacity=rc.CAPACITY_MM3): mine}
        state["figures"] = [_svg(rc.plot_shortage_years(runs))]
        if step["key"] == "rationing":
            state["figures"] = [_svg(rc.plot_runs({t(lang, "label.in_full"): mine}, first_year=rc.drought_window_start(mine)))]
        state["cards"] = _cards(lang, mine, without, t(lang, "label.before"), spilled)
        state["note"] = t(lang, "note.reservoir", capacity=rc.CAPACITY_MM3, a_short=without.scores.years_short, b_short=mine.scores.years_short, a_missed=without.scores.mean_shortage, b_missed=mine.scores.mean_shortage, spilled=spilled, worst=mine.scores.worst_month)  # fmt: skip
    else:
        in_full = _reference("full", key)
        plan_label = t(lang, "label.plan", trigger=mine.plan.trigger, ration=mine.plan.ration * 100)
        runs = {t(lang, "label.in_full"): in_full, f"{yours}: {plan_label}": mine}
        state["figures"] = [_svg(rc.plot_runs(runs, first_year=rc.drought_window_start(in_full)))]
        state["cards"] = _cards(lang, mine, in_full, t(lang, "label.in_full_short"), spilled)
        state["note"] = t(lang, "note.rationing", lowest=float(mine.storage.min()), a_worst=in_full.scores.worst_month, b_worst=mine.scores.worst_month, a_missed=in_full.scores.mean_shortage, b_missed=mine.scores.mean_shortage)  # fmt: skip

    if not built:
        todo(f"hint.{step['key']}")
    elif step["key"] == "rationing" and not _rations(mine.plan.__dict__):
        todo("hint.set_rule")
    else:
        state["done"] = True
        state["messages"].append({"level": "ok", "text": t(lang, f"step.{step['key']}.done")})
    return state
