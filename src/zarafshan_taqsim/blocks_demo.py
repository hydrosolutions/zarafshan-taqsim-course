"""TaqSim block by block: one small river system that uses every kind of block once, with its rule beside it.

The coursebook `docs/taqsim_blocks_coursebook.qmd` and the game page `workshop/blocks_game/` are built from this module.
The system runs on TaqSim v0.1.4, the version every other notebook of the course uses.

    river ──▶ canyon ──▶ headworks ──▶ canal ──▶ reservoir ──▶ farm ──▶ drain
   (Source)  (Reach)   (Splitter)  │ (Reach)   (Storage)   (Demand)  (Sink)
                                   └──▶ turbine ──▶ river_end
                                     (PassThrough)   (Sink)
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import ClassVar

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from taqsim import (
    Demand,
    Edge,
    Frequency,
    PassThrough,
    Reach,
    Sink,
    Source,
    Splitter,
    Storage,
    Strategy,
    TimeSeries,
    Timestep,
    WaterSystem,
)
from taqsim.node import (
    EVAPORATION,
    SEEPAGE,
    DeficitRecorded,
    WaterConsumed,
    WaterGenerated,
    WaterInTransit,
    WaterLost,
    WaterOutput,
    WaterPassedThrough,
    WaterReceived,
    WaterReleased,
    WaterSpilled,
    WaterStored,
)

# --- The numbers ------------------------------------------------------------------------------------------------
MONTHS: tuple[str, ...] = ("Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep")
# River inflow at Ravatkhoja, Mm³ per month, median of 2010-2023 (data/ZRB_baseline/inflow/), October first.
INFLOW_MM3: tuple[float, ...] = (203.0, 162.9, 133.5, 124.3, 106.2, 124.2, 155.6, 381.5, 771.1, 993.4, 711.9, 350.5)
# Irrigation need of the Kattakurgan district, Mm³ per month, October first.
FARM_NEED_MM3: tuple[float, ...] = (18.8, 0.0, 0.0, 0.0, 0.0, 3.3, 18.5, 38.6, 43.0, 83.0, 113.4, 66.8)
CAPACITY_MM3 = 667.0  # the Kattakurgan reservoir
DEAD_STORAGE_MM3 = 66.7  # below this the valve cannot reach
START_STORAGE_MM3 = 170.0  # on the first of October
EFFICIENCY = 0.85  # of the water that reaches the farm's gate, this share reaches the plants
EVAPORATION_SHARE = 0.03  # of the stored water, lost each month
LAG_MONTHS = 1  # the canyon: water needs one month to get through
YEARS = 3  # the run; the last year is reported, after the reservoir has settled


@dataclass(frozen=True)
class Knobs:
    """The five numbers a player can turn: one per block that has a rule with a number in it."""

    canal_share: float = 0.2  # Splitter: share of the river sent into the canal
    canal_seepage: float = 0.1  # Reach (canal): share of the flow lost to the ground
    release_cap: float = 60.0  # Storage: the valve releases what the farm needs, at most this much, Mm³ per month
    turbine_capacity: float = 600.0  # PassThrough: what the turbine can take, Mm³ per month; the rest spills
    consumption: float = 0.7  # Demand: share of the delivered water the crops use up; the rest drains back


KNOB_VALUES: dict[str, tuple[float, ...]] = {
    "canal_share": (0.05, 0.1, 0.2, 0.35, 0.5),
    "canal_seepage": (0.0, 0.1, 0.2),
    "release_cap": (20.0, 60.0, 120.0),
    "turbine_capacity": (300.0, 600.0, 1000.0),
    "consumption": (0.4, 0.7, 1.0),
}
DEFAULT_KNOBS = Knobs()

# --- The rules: one small class per block that decides something -------------------------------------------------


@dataclass(frozen=True)
class LagRouting:
    """Reach routing: water that enters this month comes out `months` later, unchanged. A corridor, not a pipe."""

    months: int = LAG_MONTHS

    def initial_state(self, reach: Reach) -> list[float]:
        return [0.0] * self.months

    def route(self, reach: Reach, inflow: float, state: list[float], t: Timestep) -> tuple[float, list[float]]:
        if not state:  # no lag: straight through
            return inflow, state
        return state[0], state[1:] + [inflow]

    def storage(self, state: list[float]) -> float:
        return float(sum(state))


@dataclass(frozen=True)
class SeepageLoss:
    """Reach loss: a share of what flows through sinks into the ground."""

    share: float = 0.1

    def calculate(self, reach: Reach, flow: float, t: Timestep) -> dict:
        return {SEEPAGE: flow * self.share}


@dataclass(frozen=True)
class CanalShare(Strategy):
    """Splitter rule: a fixed share into the canal, the rest on down the river."""

    __params__: ClassVar[tuple[str, ...]] = ("share",)
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {"share": (0.0, 1.0)}
    share: float = 0.2

    def split(self, node: Splitter, amount: float, t: Timestep) -> dict[str, float]:
        return {"canal": amount * self.share, "turbine": amount * (1.0 - self.share)}


@dataclass(frozen=True)
class ReleaseTheNeed(Strategy):
    """Storage rule: open the valve for what the farm needs this month, but the valve has a maximum."""

    __params__: ClassVar[tuple[str, ...]] = ("cap",)
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {"cap": (0.0, 200.0)}
    cap: float = 80.0
    need: tuple[float, ...] = FARM_NEED_MM3

    def release(self, node: Storage, inflow: float, t: Timestep) -> float:
        wanted = self.need[t.index % len(self.need)]
        available = max(node.storage - node.dead_storage, 0.0)
        return min(wanted, self.cap, available)


@dataclass(frozen=True)
class Evaporation:
    """Storage loss: a share of the stored water goes up as vapour each month. Not a Strategy: nothing to optimise."""

    share: float = EVAPORATION_SHARE

    def calculate(self, node: Storage, t: Timestep) -> dict:
        return {EVAPORATION: node.storage * self.share}


def rule_card(obj) -> object:
    """The source code of a rule (or any function or class), shown as a code block in a notebook."""
    import inspect

    from IPython.display import Markdown

    return Markdown(f"```python\n{inspect.getsource(obj)}```")


# --- The network --------------------------------------------------------------------------------------------------
BLOCK_KIND: dict[str, str] = {
    "river": "Source",
    "canyon": "Reach",
    "headworks": "Splitter",
    "canal": "Reach",
    "reservoir": "Storage",
    "farm": "Demand",
    "drain": "Sink",
    "turbine": "PassThrough",
    "river_end": "Sink",
}
EDGES: tuple[tuple[str, str], ...] = (
    ("river", "canyon"),
    ("canyon", "headworks"),
    ("headworks", "canal"),
    ("headworks", "turbine"),
    ("canal", "reservoir"),
    ("reservoir", "farm"),
    ("farm", "drain"),
    ("turbine", "river_end"),
)
EDGE_IDS: tuple[str, ...] = tuple(f"{a}_to_{b}" for a, b in EDGES)


def build_demo(knobs: Knobs = DEFAULT_KNOBS, years: int = YEARS) -> WaterSystem:
    """The nine blocks, wired. Each block is given its rule here; the rule is what the block does every month."""
    system = WaterSystem(frequency=Frequency.MONTHLY)
    system.add_node(Source(id="river", inflow=TimeSeries(values=list(INFLOW_MM3) * years)))
    system.add_node(Reach(id="canyon", routing_model=LagRouting(), loss_rule=SeepageLoss(share=0.0)))
    system.add_node(Splitter(id="headworks", split_policy=CanalShare(share=knobs.canal_share)))
    system.add_node(Reach(id="canal", routing_model=LagRouting(months=0), loss_rule=SeepageLoss(knobs.canal_seepage)))
    system.add_node(
        Storage(
            id="reservoir",
            capacity=CAPACITY_MM3,
            dead_storage=DEAD_STORAGE_MM3,
            initial_storage=START_STORAGE_MM3,
            release_policy=ReleaseTheNeed(cap=knobs.release_cap),
            loss_rule=Evaporation(),
        )
    )
    system.add_node(
        Demand(
            id="farm",
            requirement=TimeSeries(values=list(FARM_NEED_MM3) * years),
            consumption_fraction=knobs.consumption,
            efficiency=EFFICIENCY,
        )
    )
    system.add_node(Sink(id="drain"))
    system.add_node(PassThrough(id="turbine", capacity=knobs.turbine_capacity))
    system.add_node(Sink(id="river_end"))
    for a, b in EDGES:
        system.add_edge(Edge(id=f"{a}_to_{b}", source=a, target=b))
    system.validate()
    return system


# --- Reading a run -----------------------------------------------------------------------------------------------


def monthly(node, event_type, steps: int, field: str = "amount", **match) -> np.ndarray:
    """Sum one kind of event per step; `match` filters on event fields (e.g. source_id="river_to_canyon")."""
    out = np.zeros(steps)
    for event in node.events_of_type(event_type):
        if all(getattr(event, key) == value for key, value in match.items()):
            out[event.t] += getattr(event, field)
    return out


@dataclass(frozen=True)
class BlockRun:
    """What happened in the reported year, month by month, block by block."""

    knobs: Knobs
    flows: dict[str, np.ndarray]  # edge id -> Mm³ per month carried along that edge
    series: dict[str, dict[str, np.ndarray]]  # node id -> {quantity: Mm³ per month}
    storage_level: np.ndarray  # reservoir content at the end of each month
    transit_level: np.ndarray  # water inside the canyon at the end of each month
    first_step: int = field(default=0)  # the step the reported year starts at


def _level_path(start: float, stored: np.ndarray, lost: np.ndarray, released: np.ndarray) -> np.ndarray:
    """Content at the end of each step: `WaterStored` is what entered the store that step, not the level."""
    return start + np.cumsum(stored - lost - released)


def storage_change(run: BlockRun) -> np.ndarray:
    """Month by month: what the reservoir gained (stored minus evaporated minus released)."""
    s = run.series["reservoir"]
    return s["stored"] - s["evaporated"] - s["released"]


def transit_change(run: BlockRun) -> np.ndarray:
    """Month by month: what the canyon kept back (entered minus exited)."""
    s = run.series["canyon"]
    return s["entered"] - s["exited"]


def simulate_demo(knobs: Knobs = DEFAULT_KNOBS, years: int = YEARS) -> BlockRun:
    """Run the system and read the last year off the events."""
    system = build_demo(knobs, years)
    steps = 12 * years
    system.simulate(steps)
    n = system.nodes
    window = slice(steps - 12, steps)
    flows = {}
    for a, b in EDGES:
        flows[f"{a}_to_{b}"] = monthly(n[b], WaterReceived, steps, source_id=f"{a}_to_{b}")[window]
    stored = monthly(n["reservoir"], WaterStored, steps)
    evaporated = monthly(n["reservoir"], WaterLost, steps)
    released = monthly(n["reservoir"], WaterReleased, steps)
    spilled = monthly(n["reservoir"], WaterSpilled, steps)
    level = _level_path(START_STORAGE_MM3, stored, evaporated, released)
    series = {
        "river": {"generated": monthly(n["river"], WaterGenerated, steps)},
        "canyon": {
            "entered": monthly(n["canyon"], WaterReceived, steps),
            "exited": monthly(n["canyon"], WaterOutput, steps),
            "in_transit": monthly(n["canyon"], WaterInTransit, steps),
        },
        "headworks": {"received": monthly(n["headworks"], WaterReceived, steps)},
        "canal": {
            "entered": monthly(n["canal"], WaterReceived, steps),
            "seepage": monthly(n["canal"], WaterLost, steps),
            "exited": monthly(n["canal"], WaterOutput, steps),
        },
        "reservoir": {
            "received": monthly(n["reservoir"], WaterReceived, steps),
            "stored": stored,
            "spilled": spilled,
            "evaporated": evaporated,
            "released": released,
        },
        "farm": {
            "required": np.array(list(FARM_NEED_MM3) * years, dtype=float),
            "received": monthly(n["farm"], WaterReceived, steps),
            "inefficiency": monthly(n["farm"], WaterLost, steps),
            "consumed": monthly(n["farm"], WaterConsumed, steps),
            "deficit": monthly(n["farm"], DeficitRecorded, steps, field="deficit"),
            "returned": monthly(n["farm"], WaterOutput, steps),
        },
        "turbine": {
            "received": monthly(n["turbine"], WaterReceived, steps),
            "passed": monthly(n["turbine"], WaterPassedThrough, steps),
            "spilled": monthly(n["turbine"], WaterSpilled, steps),
        },
        "drain": {"received": monthly(n["drain"], WaterReceived, steps)},
        "river_end": {"received": monthly(n["river_end"], WaterReceived, steps)},
    }
    series = {node: {k: v[window] for k, v in d.items()} for node, d in series.items()}
    return BlockRun(
        knobs=knobs,
        flows=flows,
        series=series,
        storage_level=level[window],
        transit_level=monthly(n["canyon"], WaterInTransit, steps)[window],
        first_step=steps - 12,
    )


def balance_table(run: BlockRun) -> pd.DataFrame:
    """One row per block for the year: what came in, and where it went. `closes` is in minus the rest, in Mm³.

    `out` is what went on to the next block (a full reservoir's overflow travels on, so it counts as out);
    `left` is water that left the model at a gate, which TaqSim records as spilled and does not follow further;
    a Sink's `out` is what it took out of the system.
    """
    s = run.series
    stored_in_year = float(storage_change(run).sum())
    kept_in_canyon = float(transit_change(run).sum())
    rows = [
        ("river", "Source", s["river"]["generated"].sum(), run.flows["river_to_canyon"].sum(), 0, 0, 0, 0),
        (
            "canyon",
            "Reach",
            s["canyon"]["entered"].sum(),
            s["canyon"]["exited"].sum(),
            0,
            0,
            0,
            kept_in_canyon,
        ),
        (
            "headworks",
            "Splitter",
            s["headworks"]["received"].sum(),
            run.flows["headworks_to_canal"].sum() + run.flows["headworks_to_turbine"].sum(),
            0,
            0,
            0,
            0,
        ),
        (
            "canal",
            "Reach",
            s["canal"]["entered"].sum(),
            s["canal"]["exited"].sum(),
            0,
            s["canal"]["seepage"].sum(),
            0,
            0,
        ),
        (
            "reservoir",
            "Storage",
            s["reservoir"]["received"].sum(),
            s["reservoir"]["released"].sum() + s["reservoir"]["spilled"].sum(),
            0,
            s["reservoir"]["evaporated"].sum(),
            0,
            stored_in_year,
        ),
        (
            "farm",
            "Demand",
            s["farm"]["received"].sum(),
            s["farm"]["returned"].sum(),
            s["farm"]["consumed"].sum(),
            s["farm"]["inefficiency"].sum(),
            0,
            0,
        ),
        ("drain", "Sink", s["drain"]["received"].sum(), s["drain"]["received"].sum(), 0, 0, 0, 0),
        (
            "turbine",
            "PassThrough",
            s["turbine"]["received"].sum(),
            s["turbine"]["passed"].sum(),
            0,
            0,
            s["turbine"]["spilled"].sum(),
            0,
        ),
        ("river_end", "Sink", s["river_end"]["received"].sum(), s["river_end"]["received"].sum(), 0, 0, 0, 0),
    ]
    table = pd.DataFrame(rows, columns=["block", "kind", "in", "out", "consumed", "lost", "left", "stored"])
    table["closes"] = table["in"] - table[["out", "consumed", "lost", "left", "stored"]].sum(axis=1)
    numbers = table.columns[2:]
    table[numbers] = table[numbers].astype(float).where(table[numbers].abs() > 1e-9, 0.0)  # no "-0.0"
    return table


def system_balance(run: BlockRun) -> dict[str, float]:
    """The whole system for the year: river in = sinks out + consumed + lost + left at a gate + change in storage."""
    t = balance_table(run).set_index("block")
    return {
        "river": float(t.loc["river", "in"]),
        "to_sinks": float(t.loc[["drain", "river_end"], "in"].sum()),
        "consumed": float(t["consumed"].sum()),
        "lost": float(t["lost"].sum()),
        "left": float(t["left"].sum()),
        "stored": float(t["stored"].sum()),
    }


# --- The grid behind the game -------------------------------------------------------------------------------------


def knob_grid() -> list[Knobs]:
    names = list(KNOB_VALUES)
    return [Knobs(**dict(zip(names, values, strict=True))) for values in itertools.product(*KNOB_VALUES.values())]


# What the game stores per run, each as 12 monthly values in tenths of Mm³ (integers keep the page small)
PAYLOAD_COLUMNS: tuple[str, ...] = EDGE_IDS + (
    "storage_level",
    "transit_level",
    "canal.seepage",
    "reservoir.spilled",
    "reservoir.evaporated",
    "reservoir.released",
    "farm.consumed",
    "farm.inefficiency",
    "farm.deficit",
    "turbine.spilled",
)


def _column(run: BlockRun, name: str) -> np.ndarray:
    if name in run.flows:
        return run.flows[name]
    if name == "storage_level":
        return run.storage_level
    if name == "transit_level":
        return run.transit_level
    node, quantity = name.split(".")
    return run.series[node][quantity]


def run_payload(run: BlockRun) -> list[int]:
    """One run as a flat list: column after column, twelve tenths-of-Mm³ integers each (see PAYLOAD_COLUMNS)."""
    return [int(round(float(v) * 10)) for name in PAYLOAD_COLUMNS for v in _column(run, name)]


def game_payload(grid: list[Knobs] | None = None, years: int = YEARS) -> dict:
    """Every knob combination run through TaqSim, the last year of each, in the shape the game page reads."""
    grid = knob_grid() if grid is None else grid
    runs = [
        {"knobs": [getattr(k, name) for name in KNOB_VALUES], "data": run_payload(simulate_demo(k, years))}
        for k in grid
    ]
    return {
        "months": list(MONTHS),
        "knob_names": list(KNOB_VALUES),
        "knob_values": {k: list(v) for k, v in KNOB_VALUES.items()},
        "default_knobs": [getattr(DEFAULT_KNOBS, name) for name in KNOB_VALUES],
        "columns": list(PAYLOAD_COLUMNS),
        "scale": 10,
        "constants": {
            "capacity": CAPACITY_MM3,
            "dead_storage": DEAD_STORAGE_MM3,
            "start_storage": START_STORAGE_MM3,
            "efficiency": EFFICIENCY,
            "evaporation_share": EVAPORATION_SHARE,
            "lag_months": LAG_MONTHS,
            "inflow": list(INFLOW_MM3),
            "farm_need": list(FARM_NEED_MM3),
        },
        "block_kind": dict(BLOCK_KIND),
        "edges": [list(e) for e in EDGES],
        "runs": runs,
    }


# --- Figures -------------------------------------------------------------------------------------------------------
INK, SECONDARY, MUTED = "#1f2a33", "#4a5560", "#6b6a66"
WATER, SHORTAGE, GREEN, AMBER = "#2a78d6", "#d95926", "#1baf7a", "#d9a326"
SURFACE, GRID, AXIS = "#fbfbf9", "#e6e5df", "#b8b7ae"
KIND_COLOUR: dict[str, str] = {
    "Source": "#2a78d6",
    "Reach": "#5aa9e6",
    "Splitter": "#d9a326",
    "Storage": "#1f5fa8",
    "Demand": "#1baf7a",
    "PassThrough": "#8a7ccf",
    "Sink": "#6b6a66",
}
_RC = {
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 9.5,
    "axes.titlesize": 10.5,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.titlecolor": INK,
    "axes.titlepad": 8.0,
    "axes.labelsize": 9.0,
    "axes.labelcolor": SECONDARY,
    "axes.edgecolor": AXIS,
    "axes.linewidth": 0.8,
    "axes.facecolor": SURFACE,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "xtick.labelsize": 8.5,
    "ytick.labelsize": 8.5,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "legend.fontsize": 8.5,
    "legend.frameon": False,
    "figure.dpi": 150,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
    "svg.fonttype": "none",
}


def _styled(draw):
    def wrapped(*args, **kwargs):
        with mpl.rc_context(_RC):
            return draw(*args, **kwargs)

    wrapped.__name__, wrapped.__doc__ = draw.__name__, draw.__doc__
    return wrapped


# Where each block sits in the drawings (x, y), and what it is in one everyday picture
LAYOUT: dict[str, tuple[float, float]] = {
    "river": (0.0, 1.0),
    "canyon": (1.3, 1.0),
    "headworks": (2.6, 1.0),
    "canal": (3.9, 1.7),
    "reservoir": (5.2, 1.7),
    "farm": (6.5, 1.7),
    "drain": (7.8, 1.7),
    "turbine": (4.55, 0.3),
    "river_end": (7.8, 0.3),
}
ANALOGY: dict[str, str] = {
    "Source": "a spring: water appears, from a list of numbers",
    "Reach": "a corridor: water takes time to get through and some leaks away",
    "Splitter": "a fork with a traffic officer: so much this way, the rest that way",
    "Storage": "a bathtub with a valve: it fills, overflows when full, loses some as vapour, lets out what the valve says",
    "Demand": "a customer: uses up part of the water and sends the rest back",
    "PassThrough": "a gate of fixed width: what fits goes through, the rest spills",
    "Sink": "the sea: water arrives and the story ends",
}
RULE_NAME: dict[str, str] = {
    "river": "inflow series",
    "canyon": "LagRouting",
    "headworks": "CanalShare",
    "canal": "SeepageLoss",
    "reservoir": "ReleaseTheNeed + Evaporation",
    "farm": "requirement, consumption, efficiency",
    "turbine": "capacity",
    "drain": "none",
    "river_end": "none",
}


def _box(ax, xy, label, kind, highlight=False, sub=None):
    x, y = xy
    w, h = 0.78, 0.42
    colour = KIND_COLOUR[kind]
    patch = FancyBboxPatch(
        (x - w / 2, y - h / 2),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=2.2 if highlight else 1.0,
        edgecolor=INK if highlight else colour,
        facecolor=colour if kind != "Sink" else "#e9e8e2",
        alpha=0.95,
    )
    ax.add_patch(patch)
    text_colour = "white" if kind != "Sink" else INK
    ax.text(x, y + 0.06, label, ha="center", va="center", fontsize=9, fontweight="bold", color=text_colour)
    ax.text(x, y - 0.1, kind, ha="center", va="center", fontsize=7.5, color=text_colour, alpha=0.9)
    if sub:
        ax.text(x, y - h / 2 - 0.09, sub, ha="center", va="top", fontsize=7.5, color=SECONDARY)


def _arrow(ax, a, b, label=None, width=1.0):
    (x0, y0), (x1, y1) = LAYOUT[a], LAYOUT[b]
    dx = 0.42
    start = (x0 + dx, y0)
    end = (x1 - dx, y1)
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=max(0.8, width),
            color=WATER,
            connectionstyle="arc3,rad=0.0" if y0 == y1 else "angle3,angleA=0,angleB=90" if x1 > x0 else "arc3",
            zorder=1,
        )
    )
    if label is not None:
        mx, my = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
        if y0 != y1:
            my = (y0 + y1) / 2 + (0.1 if y1 > y0 else -0.1)
        ax.text(
            mx,
            my + 0.08,
            label,
            ha="center",
            va="bottom",
            fontsize=7.5,
            color=INK,
            zorder=3,
            bbox={"boxstyle": "round,pad=0.15", "facecolor": "white", "edgecolor": "none", "alpha": 0.85},
        )


@_styled
def plot_demo_network(run: BlockRun | None = None, month: int | None = None, highlight: str | None = None) -> Figure:
    """The nine blocks and eight edges. With a run and a month, every edge carries that month's flow in Mm³."""
    fig, ax = plt.subplots(figsize=(11.5, 3.6))
    ax.set_axis_off()
    ax.set_xlim(-0.6, 8.4)
    ax.set_ylim(-0.3, 2.3)
    ax.grid(False)
    for a, b in EDGES:
        label, width = None, 1.0
        if run is not None and month is not None:
            flow = float(run.flows[f"{a}_to_{b}"][month])
            label, width = f"{flow:,.0f}", 0.8 + 4.0 * flow / max(INFLOW_MM3)
        _arrow(ax, a, b, label, width)
    for node, kind in BLOCK_KIND.items():
        sub = None
        if run is not None and month is not None and node == "reservoir":
            sub = f"holds {run.storage_level[month]:,.0f} of {CAPACITY_MM3:,.0f}"
        if run is not None and month is not None and node == "farm":
            d = run.series["farm"]["deficit"][month]
            sub = "all it needs" if d < 0.05 else f"short by {d:,.0f}"
        if (
            run is not None
            and month is not None
            and node == "turbine"
            and run.series["turbine"]["spilled"][month] > 0.05
        ):
            sub = f"spills {run.series['turbine']['spilled'][month]:,.0f}"
        if run is not None and month is not None and node == "canyon":
            sub = f"inside: {run.transit_level[month]:,.0f}"
        _box(ax, LAYOUT[node], node, kind, highlight=(node == highlight), sub=sub)
    title = "The demo system: nine blocks of seven kinds"
    if run is not None and month is not None:
        title = f"{MONTHS[month]}: water on every edge, Mm³"
    ax.set_title(title)
    fig.tight_layout()
    return fig


@_styled
def plot_block_catalogue() -> Figure:
    """The seven kinds of block, each with its everyday picture and the question its rule answers."""
    fig, ax = plt.subplots(figsize=(11.5, 4.4))
    ax.set_axis_off()
    ax.grid(False)
    ax.set_xlim(0, 11.5)
    ax.set_ylim(0, 4.3)
    questions = {
        "Source": "How much comes in each month?\n(a list of numbers)",
        "Reach": "How long does it take, how much leaks?\n(a routing model, a loss rule)",
        "Splitter": "How much goes which way?\n(a split rule)",
        "Storage": "How much to let out, what is lost?\n(a release rule, a loss rule)",
        "Demand": "How much is needed, used up, lost on the way?\n(requirement, consumption, efficiency)",
        "PassThrough": "How much fits through?\n(a capacity)",
        "Sink": "Nothing to decide.",
    }
    for i, (kind, picture) in enumerate(ANALOGY.items()):
        y = 3.9 - i * 0.58
        ax.add_patch(
            FancyBboxPatch(
                (0.15, y - 0.2),
                1.5,
                0.4,
                boxstyle="round,pad=0.02,rounding_size=0.08",
                facecolor=KIND_COLOUR[kind] if kind != "Sink" else "#e9e8e2",
                edgecolor="none",
            )
        )
        ax.text(
            0.9,
            y,
            kind,
            ha="center",
            va="center",
            fontsize=9,
            fontweight="bold",
            color="white" if kind != "Sink" else INK,
        )
        ax.text(
            1.85,
            y + 0.08,
            picture.split(":")[0].capitalize() + ":",
            ha="left",
            va="center",
            fontsize=9,
            fontweight="bold",
            color=INK,
        )
        ax.text(1.85, y - 0.12, picture.split(":", 1)[1].strip(), ha="left", va="center", fontsize=8.5, color=SECONDARY)
        ax.text(7.6, y, questions[kind], ha="left", va="center", fontsize=8.5, color=INK, linespacing=1.3)
    ax.text(1.85, 4.2, "The picture", fontsize=8, color=MUTED, va="bottom")
    ax.text(7.6, 4.2, "The question its rule answers", fontsize=8, color=MUTED, va="bottom")
    fig.tight_layout()
    return fig


@_styled
def plot_months(
    series: dict[str, np.ndarray],
    title: str,
    unit: str = "Mm³ per month",
    kind: str = "line",
    stacked: bool = False,
    colours: dict[str, str] | None = None,
    reference: tuple[str, np.ndarray] | None = None,
) -> Figure:
    """A small chart of monthly series: lines, bars or stacked bars, October first."""
    fig, ax = plt.subplots(figsize=(8.5, 3.2))
    x = np.arange(12)
    colours = colours or {}
    palette = [WATER, SHORTAGE, GREEN, AMBER, "#8a7ccf", MUTED]
    if kind == "line":
        for i, (name, values) in enumerate(series.items()):
            ax.plot(
                x, values, marker="o", ms=3.5, lw=1.8, color=colours.get(name, palette[i % len(palette)]), label=name
            )
    else:
        n = len(series)
        bottom = np.zeros(12)
        width = 0.7 if stacked else 0.7 / n
        for i, (name, values) in enumerate(series.items()):
            offset = 0 if stacked else (i - (n - 1) / 2) * width
            ax.bar(
                x + offset,
                values,
                width,
                bottom=bottom if stacked else None,
                color=colours.get(name, palette[i % len(palette)]),
                label=name,
            )
            if stacked:
                bottom = bottom + values
    if reference is not None:
        ax.step(x, reference[1], where="mid", color=INK, lw=1.2, ls="--", label=reference[0])
    ax.set_xticks(x, MONTHS)
    ax.set_ylabel(unit)
    ax.set_title(title)
    ax.legend(ncol=min(len(series) + (reference is not None), 4), loc="upper left")
    fig.tight_layout()
    return fig


@_styled
def plot_where_the_water_went(run: BlockRun) -> Figure:
    """Each month's river water, split by where it ended up in that month (a stacked bar), against the river itself."""
    s = run.series
    parts = {
        "river end, through the turbine": run.flows["turbine_to_river_end"],
        "spilled past the turbine": s["turbine"]["spilled"],
        "kept in the canyon for next month": transit_change(run),
        "put into the reservoir": storage_change(run),
        "evaporated": s["reservoir"]["evaporated"],
        "seepage in the canal": s["canal"]["seepage"],
        "lost on the farm": s["farm"]["inefficiency"],
        "used by the crops": s["farm"]["consumed"],
        "drained back": run.flows["farm_to_drain"],
    }
    colours = {
        "river end, through the turbine": WATER,
        "spilled past the turbine": "#9dc3ea",
        "kept in the canyon for next month": "#8fb6dd",
        "put into the reservoir": "#1f5fa8",
        "evaporated": AMBER,
        "seepage in the canal": "#e3c76d",
        "lost on the farm": "#f0b08a",
        "used by the crops": GREEN,
        "drained back": "#9fdcc4",
    }
    fig, ax = plt.subplots(figsize=(10.5, 4.2))
    x = np.arange(12)
    positive = np.zeros(12)
    negative = np.zeros(12)
    for name, values in parts.items():
        up = np.where(values >= 0, values, 0.0)
        down = np.where(values < 0, values, 0.0)
        ax.bar(x, up, 0.72, bottom=positive, color=colours[name], label=name)
        ax.bar(x, down, 0.72, bottom=negative, color=colours[name])
        positive = positive + up
        negative = negative + down
    ax.plot(x, s["river"]["generated"], color=INK, lw=1.4, ls="--", marker="o", ms=3, label="the river")
    ax.axhline(0, color=AXIS, lw=0.8)
    ax.set_xticks(x, MONTHS)
    ax.set_ylabel("Mm³ per month")
    ax.set_title("Where the water went, month by month (below zero: taken out of the canyon or the reservoir)")
    ax.legend(ncol=3, loc="upper left", fontsize=7.5)
    fig.tight_layout()
    return fig


@_styled
def plot_balance(run: BlockRun) -> Figure:
    """The year's water balance of the whole system as one bar on each side: in on the left, where it went on the right."""
    b = system_balance(run)
    fig, ax = plt.subplots(figsize=(8.5, 3.4))
    right = {
        "to the two sinks": (b["to_sinks"], WATER),
        "used by the crops": (b["consumed"], GREEN),
        "lost: seepage, evaporation, farm": (b["lost"], AMBER),
        "left at the turbine's gate": (b["left"], "#9dc3ea"),
        "change in storage": (b["stored"], "#1f5fa8"),
    }
    ax.bar(0, b["river"], 0.55, color=INK, label="the river brought")
    bottom = 0.0
    for name, (value, colour) in right.items():
        ax.bar(1, value, 0.55, bottom=bottom, color=colour, label=name)
        if abs(value) > 0.03 * b["river"]:
            ax.text(
                1,
                bottom + value / 2,
                f"{value:,.0f}",
                ha="center",
                va="center",
                fontsize=8,
                color="white" if colour != "#9dc3ea" else INK,
            )
        bottom += value
    ax.text(
        0, b["river"] / 2, f"{b['river']:,.0f}", ha="center", va="center", fontsize=9, color="white", fontweight="bold"
    )
    ax.set_xticks([0, 1], ["in", "out, used, lost, left, stored"])
    ax.set_ylabel("Mm³ in the year")
    ax.set_title("The year adds up: what the river brought equals where it all went")
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    return fig
