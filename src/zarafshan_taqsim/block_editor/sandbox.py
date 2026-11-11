"""The free sandbox: any network of the seven kinds of block, run through TaqSim.

The guided steps use the rules of the rationing lesson, which know that there is one farm. Here a network can
have any shape, so the rules are general: a reservoir releases what the Demand blocks below it ask for, a
Splitter sends a share to its first connection, a Reach delays and leaks. Time moves in months for 100 years,
volumes are in Mm³, and the river is the lesson's synthetic river, scaled.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import matplotlib.pyplot as plt
import numpy as np
from taqsim import Demand, Edge, PassThrough, Reach, Sink, Source, Splitter, Storage, Strategy, TimeSeries, WaterSystem
from taqsim.node import (
    DeficitRecorded,
    NoLoss,
    WaterConsumed,
    WaterGenerated,
    WaterLost,
    WaterOutput,
    WaterPassedThrough,
    WaterReceived,
    WaterReleased,
    WaterSpilled,
    WaterStored,
)
from taqsim.time import Frequency, Timestep

from zarafshan_taqsim import rationing_coursebook as rc
from zarafshan_taqsim.block_editor.i18n import t
from zarafshan_taqsim.blocks_demo import LagRouting, SeepageLoss

YEARS = 100
KINDS: dict[str, dict] = {
    # kind: the name a new block gets, its colour, and its numbers
    "Source": {"name": "river", "colour": "#0072B2", "params": {"regime": "central_asia", "scale": 1.0}},
    "Reach": {"name": "canal", "colour": "#56B4E9", "params": {"lag": 0, "seepage": 0.1}},
    "Splitter": {"name": "headworks", "colour": "#E69F00", "params": {"share": 0.5}},
    "Storage": {"name": "reservoir", "colour": "#CC79A7", "params": {"capacity": 40, "initial_storage": 20, "trigger": 0, "ration": 1.0, "evaporation": 0.0}},
    "Demand": {"name": "farm", "colour": "#009E73", "params": {"summer_need": 45, "winter_need": 5, "efficiency": 1.0, "consumption": 1.0}},
    "PassThrough": {"name": "gate", "colour": "#D55E00", "params": {"gate_capacity": 6}},
    "Sink": {"name": "outlet", "colour": "#595959", "params": {}},
}  # fmt: skip
# Blocks that arrive from the guided steps with a meaning of their own
NAMED_PARAMS: dict[str, dict] = {"winter_fields": {"summer_need": 0, "winter_need": 15}}
FIELDS: dict[str, list[dict]] = {
    "Source": [
        {"key": "regime", "type": "choice", "options": ["central_asia", "paper"]},
        {"key": "scale", "min": 0.5, "max": 3, "step": 0.25, "percent": True},
    ],
    "Reach": [
        {"key": "lag", "min": 0, "max": 3, "step": 1, "unit": ""},
        {"key": "seepage", "min": 0, "max": 0.3, "step": 0.05, "percent": True},
    ],
    "Splitter": [{"key": "share", "min": 0, "max": 1, "step": 0.05, "percent": True}],
    "Storage": [
        {"key": "capacity", "min": 10, "max": 200, "step": 5, "unit": "Mm³"},
        {"key": "initial_storage", "min": 0, "max": 200, "step": 5, "unit": "Mm³", "max_from": "capacity"},
        {"key": "trigger", "min": 0, "max": 200, "step": 1, "unit": "Mm³", "max_from": "capacity", "group": "rule"},
        {"key": "ration", "min": 0, "max": 1, "step": 0.05, "percent": True, "group": "rule"},
        {"key": "evaporation", "min": 0, "max": 0.06, "step": 0.01, "percent": True, "group": "loss"},
    ],
    "Demand": [
        {"key": "summer_need", "min": 0, "max": 100, "step": 5, "unit": "Mm³"},
        {"key": "winter_need", "min": 0, "max": 30, "step": 1, "unit": "Mm³"},
        {"key": "efficiency", "min": 0.5, "max": 1, "step": 0.05, "percent": True},
        {"key": "consumption", "min": 0, "max": 1, "step": 0.1, "percent": True},
    ],
    "PassThrough": [{"key": "gate_capacity", "min": 1, "max": 30, "step": 1, "unit": "Mm³"}],
    "Sink": [],
}
PORTS: dict[str, tuple[bool, bool]] = {  # kind: (takes water in, sends water on)
    "Source": (False, True), "Reach": (True, True), "Splitter": (True, True), "Storage": (True, True),
    "Demand": (True, True), "PassThrough": (True, True), "Sink": (True, False),
}  # fmt: skip


# --- Rules ----------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ReleaseForDemands(Strategy):
    """Release what the Demand blocks below the reservoir ask for this month.

    In summer, when the reservoir holds less than the trigger, release only the ration of it.
    """

    __params__: ClassVar[tuple[str, ...]] = ("trigger", "ration")
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {"trigger": (0.0, 200.0), "ration": (0.0, 1.0)}

    trigger: float = 0.0
    ration: float = 1.0
    need: tuple[float, ...] = (0.0,) * 12  # what the blocks below ask for in each month of the year, Mm³

    def release(self, node: Storage, inflow: float, t: Timestep) -> float:
        month = t.index % 12  # 0-5 = winter, 6-11 = summer
        need = self.need[month]
        if month in rc.SUMMER_MONTHS and node.storage < self.trigger:
            need *= self.ration
        return min(need, node.storage)


@dataclass(frozen=True)
class ShareSplit:
    """Send a fixed share to the first connected block; the others share the rest equally."""

    share: float
    targets: tuple[str, ...]

    def split(self, node: Splitter, amount: float, t: Timestep) -> dict[str, float]:
        if len(self.targets) == 1:
            return {self.targets[0]: amount}
        rest = amount * (1.0 - self.share) / (len(self.targets) - 1)
        return {target: amount * self.share if i == 0 else rest for i, target in enumerate(self.targets)}


# --- From a drawing to a system -------------------------------------------------------------------------------


def params_of(node: dict) -> dict:
    """A block's numbers, with the defaults of its kind for those it does not carry."""
    return {**KINDS[node["kind"]]["params"], **NAMED_PARAMS.get(node["id"], {}), **node.get("params", {})}


def _need(params: dict) -> tuple[float, ...]:
    return (float(params["winter_need"]) / 6.0,) * 6 + (float(params["summer_need"]) / 6.0,) * 6


def _below(graph: dict, start: str) -> list[dict]:
    """Every block the water can reach from `start`."""
    nodes = {node["id"]: node for node in graph["nodes"]}
    seen, queue = [], [start]
    while queue:
        for edge in graph["edges"]:
            if edge["source"] == queue[0] and edge["target"] not in seen:
                seen.append(edge["target"])
                queue.append(edge["target"])
        queue.pop(0)
    return [nodes[name] for name in seen if name in nodes]


def need_below(graph: dict, node_id: str) -> tuple[float, ...]:
    """What the Demand blocks below a block ask for at their inlet, per month of the year."""
    total = np.zeros(12)
    for node in _below(graph, node_id):
        if node["kind"] == "Demand":
            params = params_of(node)
            total += np.asarray(_need(params)) / max(float(params["efficiency"]), 1e-9)
    return tuple(float(value) for value in total)


def check(graph: dict) -> list[tuple[str, str]]:
    """What keeps the drawing from running: (message key, block id) pairs. An empty list means it can run."""
    nodes = graph.get("nodes", [])
    if not nodes:
        return [("problem.empty", "")]
    problems = []
    kinds = {node["kind"] for node in nodes}
    if "Source" not in kinds:
        problems.append(("problem.no_source_kind", ""))
    if "Sink" not in kinds:
        problems.append(("problem.no_sink_kind", ""))
    for node in nodes:
        takes, sends = PORTS[node["kind"]]
        if sends and not any(edge["source"] == node["id"] for edge in graph["edges"]):
            problems.append(("problem.no_way_out", node["id"]))
        if takes and not any(edge["target"] == node["id"] for edge in graph["edges"]):
            problems.append(("problem.no_way_in", node["id"]))
    return problems


def inflows_of(params: dict) -> tuple[float, ...]:
    regime = rc.REGIMES.get(str(params["regime"]), rc.CENTRAL_ASIA_REGIME)
    return tuple(float(params["scale"]) * value for value in rc.synthetic_inflows(years=YEARS, seed=72, regime=regime))


def build(graph: dict) -> WaterSystem:
    """Build and validate the TaqSim system the drawing describes."""
    system = WaterSystem(frequency=Frequency.MONTHLY)
    for node in graph["nodes"]:
        node_id, kind, params = node["id"], node["kind"], params_of(node)
        if kind == "Source":
            system.add_node(Source(id=node_id, inflow=TimeSeries(values=list(inflows_of(params)))))
        elif kind == "Reach":
            system.add_node(Reach(id=node_id, routing_model=LagRouting(months=int(params["lag"])), loss_rule=SeepageLoss(share=float(params["seepage"]))))
        elif kind == "Splitter":
            targets = tuple(edge["target"] for edge in graph["edges"] if edge["source"] == node_id)
            system.add_node(Splitter(id=node_id, split_policy=ShareSplit(share=float(params["share"]), targets=targets)))
        elif kind == "Storage":
            capacity = float(params["capacity"])
            rule = ReleaseForDemands(trigger=min(float(params["trigger"]), capacity), ration=float(params["ration"]), need=need_below(graph, node_id))
            loss = rc.SummerEvaporation(share=float(params["evaporation"])) if float(params["evaporation"]) > 0 else NoLoss()
            system.add_node(Storage(id=node_id, capacity=capacity, initial_storage=min(float(params["initial_storage"]), capacity), release_policy=rule, loss_rule=loss))
        elif kind == "Demand":
            system.add_node(Demand(id=node_id, requirement=TimeSeries(values=list(_need(params)) * YEARS), consumption_fraction=float(params["consumption"]), efficiency=float(params["efficiency"])))
        elif kind == "PassThrough":
            system.add_node(PassThrough(id=node_id, capacity=float(params["gate_capacity"])))
        elif kind == "Sink":
            system.add_node(Sink(id=node_id))
    for edge in graph["edges"]:
        system.add_edge(Edge(id=f"{edge['source']}_to_{edge['target']}", source=edge["source"], target=edge["target"]))
    system.validate()
    return system


def to_python(graph: dict) -> str:
    """The drawing as Python. Running it builds the same system."""
    lines = [
        "from taqsim import Demand, Edge, PassThrough, Reach, Sink, Source, Splitter, Storage, TimeSeries, WaterSystem",
        "from taqsim.node import NoLoss",
        "from taqsim.time import Frequency",
        "from zarafshan_taqsim.block_editor.sandbox import ReleaseForDemands, ShareSplit",
        "from zarafshan_taqsim.blocks_demo import LagRouting, SeepageLoss",
        "from zarafshan_taqsim.rationing_coursebook import REGIMES, SummerEvaporation, synthetic_inflows",
        "",
        f"YEARS = {YEARS}",
        "system = WaterSystem(frequency=Frequency.MONTHLY)",
    ]
    for node in graph["nodes"]:
        node_id, kind, p = node["id"], node["kind"], params_of(node)
        if kind == "Source":
            lines += [
                f'{node_id}_flow = [{float(p["scale"]):g} * value for value in synthetic_inflows(years=YEARS, seed=72, regime=REGIMES["{p["regime"]}"])]',
                f'system.add_node(Source(id="{node_id}", inflow=TimeSeries(values={node_id}_flow)))',
            ]
        elif kind == "Reach":
            lines.append(f'system.add_node(Reach(id="{node_id}", routing_model=LagRouting(months={int(p["lag"])}), loss_rule=SeepageLoss(share={float(p["seepage"]):g})))')
        elif kind == "Splitter":
            targets = tuple(edge["target"] for edge in graph["edges"] if edge["source"] == node_id)
            lines.append(f'system.add_node(Splitter(id="{node_id}", split_policy=ShareSplit(share={float(p["share"]):g}, targets={targets!r})))')
        elif kind == "Storage":
            capacity = float(p["capacity"])
            need = ", ".join(f"{value:.4g}" for value in need_below(graph, node_id))
            loss = f'SummerEvaporation(share={float(p["evaporation"]):g})' if float(p["evaporation"]) > 0 else "NoLoss()"
            lines += [
                f"{node_id}_need = ({need})  # what the blocks below ask for, per month",
                "system.add_node(",
                "    Storage(",
                f'        id="{node_id}",',
                f"        capacity={capacity:g},",
                f'        initial_storage={min(float(p["initial_storage"]), capacity):g},',
                f'        release_policy=ReleaseForDemands(trigger={min(float(p["trigger"]), capacity):g}, ration={float(p["ration"]):g}, need={node_id}_need),',
                f"        loss_rule={loss},",
                "    )",
                ")",
            ]
        elif kind == "Demand":
            need = ", ".join(f"{value:.4g}" for value in _need(p))
            lines += [
                f"{node_id}_need = [{need}] * YEARS",
                f'system.add_node(Demand(id="{node_id}", requirement=TimeSeries(values={node_id}_need), consumption_fraction={float(p["consumption"]):g}, efficiency={float(p["efficiency"]):g}))',
            ]
        elif kind == "PassThrough":
            lines.append(f'system.add_node(PassThrough(id="{node_id}", capacity={float(p["gate_capacity"]):g}))')
        elif kind == "Sink":
            lines.append(f'system.add_node(Sink(id="{node_id}"))')
    for edge in graph["edges"]:
        lines.append(f'system.add_edge(Edge(id="{edge["source"]}_to_{edge["target"]}", source="{edge["source"]}", target="{edge["target"]}"))')
    lines += ["", "system.validate()  # check the network", "system.simulate(12 * YEARS)  # run all 1,200 months"]
    return "\n".join(lines)


# --- Reading a run --------------------------------------------------------------------------------------------


def _sum(node, event_type, field: str = "amount") -> np.ndarray:
    out = np.zeros(12 * YEARS)
    for event in node.events_of_type(event_type):
        out[event.t] += getattr(event, field)
    return out


def balance(graph: dict, system: WaterSystem) -> list[dict]:
    """One row per block, in Mm³ per year: what came in and where it went. `closes` should be zero."""
    rows = []
    for node in graph["nodes"]:
        block, kind = system.nodes[node["id"]], node["kind"]
        row = dict.fromkeys(("in", "out", "used", "lost", "left", "stored"), 0.0)
        if kind == "Source":
            row["in"] = row["out"] = _sum(block, WaterGenerated).sum()
        else:
            row["in"] = _sum(block, WaterReceived).sum()
        if kind == "Reach":
            row["out"], row["lost"] = _sum(block, WaterOutput).sum(), _sum(block, WaterLost).sum()
            row["stored"] = row["in"] - row["out"] - row["lost"]  # still on its way at the end
        elif kind in ("Splitter", "Sink"):
            row["out"] = row["in"]
        elif kind == "Storage":
            released, lost = _sum(block, WaterReleased).sum(), _sum(block, WaterLost).sum()
            row["out"], row["lost"] = released + _sum(block, WaterSpilled).sum(), lost
            row["stored"] = _sum(block, WaterStored).sum() - lost - released
        elif kind == "Demand":
            row["out"], row["used"], row["lost"] = _sum(block, WaterOutput).sum(), _sum(block, WaterConsumed).sum(), _sum(block, WaterLost).sum()
        elif kind == "PassThrough":
            row["out"], row["left"] = _sum(block, WaterPassedThrough).sum(), _sum(block, WaterSpilled).sum()
        row = {key: value / YEARS for key, value in row.items()}
        row["closes"] = row["in"] - row["out"] - row["used"] - row["lost"] - row["left"] - row["stored"]
        rows.append({"block": node["id"], "kind": kind, **row})
    return rows


def demand_run(node: dict, system: WaterSystem) -> rc.RunResult:
    """A Demand block's shortages in the shape the lesson's figures draw."""
    need = np.tile(_need(params_of(node)), YEARS)
    deficit = _sum(system.nodes[node["id"]], DeficitRecorded, "deficit")
    shortage = np.divide(deficit, need, out=np.zeros_like(deficit), where=need > 0) * 100.0
    by_year = shortage.reshape(-1, 12)
    scores = rc.Scores(
        mean_shortage=float(deficit.sum() / YEARS),
        worst_month=float(shortage.max()),
        years_short=int((by_year.max(axis=1) > rc.SHORT_TOLERANCE_PERCENT).sum()),
    )
    return rc.RunResult(plan=rc.NO_RATIONING, scores=scores, storage=np.zeros(len(need)), shortage_by_month=shortage)


def storage_path(node: dict, system: WaterSystem) -> np.ndarray:
    block = system.nodes[node["id"]]
    return block.initial_storage + np.cumsum(_sum(block, WaterStored) - _sum(block, WaterLost) - _sum(block, WaterReleased))


@rc._styled
def plot_storages(paths: dict[str, tuple[np.ndarray, float]], first_year: int, window_years: int = 20):
    """Water in each reservoir over a window of years, with its capacity as a dashed line."""
    fig, axes = plt.subplots(len(paths), 1, figsize=(8.0, 1.9 * len(paths) + 0.6), sharex=True, squeeze=False)
    months = np.arange(12 * (first_year - 1), 12 * (first_year - 1 + window_years))
    for (label, (path, capacity)), (ax,) in zip(paths.items(), axes, strict=True):
        ax.axhline(capacity, color=rc.AXIS, linewidth=0.8, linestyle=(0, (3, 3)))
        ax.plot(months / 12 + 1, path[months], color=rc.WATER, linewidth=1.3)
        ax.set_ylim(0, capacity * 1.12)
        ax.set_xlim(first_year, first_year + window_years)
        ax.set_ylabel("Water stored (Mm³)")
        ax.set_title(label, loc="left")
        rc._style(ax)
    axes[-1][0].set_xlabel(f"Year ({window_years} years around the worst shortage)")
    fig.tight_layout(h_pad=1.2)
    return fig


def evaluate(graph: dict, lang: str, svg) -> dict:
    """Check the drawing, run it if it can run, and return scores, figures, the water balance and the code."""
    state: dict = {"done": False, "messages": [], "cards": [], "figures": [], "note": "", "code": "", "table": None}
    for key, block in check(graph)[:3]:
        state["messages"].append({"level": "todo", "text": t(lang, key, block=block)})
    if state["messages"]:
        return state
    try:
        system = build(graph)
        system.simulate(12 * YEARS)
    except Exception as error:  # TaqSim's own message is better than none
        state["messages"].append({"level": "error", "text": t(lang, "problem.taqsim", error=str(error))})
        return state
    state["code"] = to_python(graph)
    state["messages"].append({"level": "ok", "text": t(lang, "sandbox.runs")})

    rows = balance(graph, system)
    total = {key: sum(row[key] for row in rows) for key in ("used", "lost", "left", "stored")}
    river = sum(row["in"] for row in rows if row["kind"] == "Source")
    to_sinks = sum(row["in"] for row in rows if row["kind"] == "Sink")
    gap = river - to_sinks - total["used"] - total["lost"] - total["left"] - total["stored"]

    def card(key: str, value: float, sub: str = "") -> dict:
        return {"label": t(lang, f"card.{key}"), "value": f"{value:.1f} Mm³", "sub": sub}

    state["cards"] = [
        card("river", river),
        card("used", total["used"]),
        card("lost", total["lost"] + total["left"]),
        card("to_sinks", to_sinks),
        card("balance_gap", 0.0 if abs(gap) < 0.05 else gap, t(lang, "card.balance_ok" if abs(gap) < 0.05 else "card.balance_off")),
    ]
    columns = ("block", "kind", "in", "out", "used", "lost", "left", "stored")
    state["table"] = {
        "columns": [t(lang, f"balance.{column}") for column in columns],
        "rows": [[row["block"], row["kind"], *(f"{row[column]:.1f}" for column in columns[2:])] for row in rows],
    }
    demands = {node["id"]: demand_run(node, system) for node in graph["nodes"] if node["kind"] == "Demand"}
    shown = {f"{name}: {t(lang, 'sandbox.demand_title')}": run for name, run in list(demands.items())[:4]}
    if shown:
        state["figures"].append(svg(rc.plot_shortage_years(shown), shown))
    storages = [node for node in graph["nodes"] if node["kind"] == "Storage"][:3]
    if storages:
        worst = max(demands.values(), key=lambda run: run.scores.worst_month, default=None)
        first_year = rc.drought_window_start(worst) if worst is not None else 1
        paths = {node["id"]: (storage_path(node, system), float(params_of(node)["capacity"])) for node in storages}
        state["figures"].append(svg(plot_storages(paths, first_year)))
    state["note"] = t(lang, "sandbox.note")
    return state


def example() -> dict:
    """A network that uses every kind of block once, as a starting point."""
    names = {"Source": "river", "Splitter": "headworks", "Reach": "canal", "Storage": "reservoir", "Demand": "farm", "PassThrough": "gate", "Sink": "outlet"}
    nodes = [{"id": name, "kind": kind, "params": dict(KINDS[kind]["params"])} for kind, name in names.items()]
    chain = [("river", "headworks"), ("headworks", "canal"), ("headworks", "gate"), ("canal", "reservoir"), ("reservoir", "farm"), ("farm", "outlet"), ("gate", "outlet")]
    return {"nodes": nodes, "edges": [{"source": a, "target": b} for a, b in chain]}
