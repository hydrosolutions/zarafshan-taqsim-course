"""Reservoir rationing coursebook: one reservoir, one farm, two knobs, one trade-off.

The system and its numbers follow the water-supply reservoir example of Hashimoto, Stedinger and Loucks (1982),
"Reliability, resiliency, and vulnerability criteria for water resource system performance evaluation", Water
Resources Research 18(1), p. 17 and Table 1, with volumes written in Mm³ (their 10^7 m³ times ten). Three things
differ from the paper and are said so in the coursebook: the two seasons are split evenly into six monthly steps,
the operating rule is a simple two-knob rationing rule (the paper derives its rules by dynamic programming), and
the synthetic river applies the paper's season-to-season correlations to the logarithms of the flows.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator
from taqsim import Demand, Edge, Objective, Sink, Source, Storage, Strategy, TimeSeries, WaterSystem, optimize
from taqsim.common import EVAPORATION
from taqsim.node import NoLoss
from taqsim.node.events import DeficitRecorded, WaterLost, WaterReleased, WaterStored
from taqsim.time import Frequency, Timestep

logger = logging.getLogger(__name__)

# --- Numbers from the paper (Hashimoto et al. 1982, p. 17 and Table 1), in Mm³ ----------------------------
CAPACITY_MM3 = 40.0
SUMMER_NEED_MM3 = 45.0
WINTER_NEED_MM3 = 5.0
YEARLY_NEED_MM3 = SUMMER_NEED_MM3 + WINTER_NEED_MM3
WINTER_TO_SUMMER_CORRELATION = 0.65
SUMMER_TO_WINTER_CORRELATION = 0.60


@dataclass(frozen=True)
class Regime:
    """The seasonal pattern of a river: mean and standard deviation of each season's total, in Mm³."""

    name: str
    winter: tuple[float, float]
    summer: tuple[float, float]
    note: str


# The paper's river peaks in winter. A Central Asian river peaks in summer (snow and glacier melt) and is lowest
# in winter; we model it by swapping the paper's two seasons, which keeps the yearly total and the spread.
PAPER_REGIME = Regime("paper", (40.0, 15.0), (25.0, 10.0), "winter peak, as in Hashimoto et al. (1982), Table 1")
CENTRAL_ASIA_REGIME = Regime(
    "central_asia", (25.0, 10.0), (40.0, 15.0), "summer peak from snow and glacier melt, winter minimum"
)
REGIMES = {regime.name: regime for regime in (PAPER_REGIME, CENTRAL_ASIA_REGIME)}
DEFAULT_REGIME = CENTRAL_ASIA_REGIME
WINTER_FLOW_MEAN, WINTER_FLOW_SD = DEFAULT_REGIME.winter
SUMMER_FLOW_MEAN, SUMMER_FLOW_SD = DEFAULT_REGIME.summer

# --- Choices made for the coursebook (not from the paper) -------------------------------------------------
YEARS = 100
# Of seeds 0-199, the one whose 100-year sample is closest to the paper's six statistics (chosen with the paper's
# regime; swapping the seasons reuses the same random draws).
SEED = 72
START_STORAGE_MM3 = 20.0
# Share of the stored water lost per summer month in the "one more block" section. Illustrative.
EVAPORATION_SHARE_EXAMPLE = 0.03
MONTHS_PER_SEASON = 6
# A year starts with the six winter months (reservoir fills), then the six summer months (the farm irrigates).
SUMMER_MONTHS = range(MONTHS_PER_SEASON, 12)
MONTHLY_NEED_MM3: tuple[float, ...] = (WINTER_NEED_MM3 / MONTHS_PER_SEASON,) * MONTHS_PER_SEASON + (
    SUMMER_NEED_MM3 / MONTHS_PER_SEASON,
) * MONTHS_PER_SEASON
SHORT_TOLERANCE_PERCENT = 1e-6
# The trade-off charts stop here on the average-shortage axis; plans beyond it are far from any sensible choice.
MEAN_SHORTAGE_AXIS_MAX = 12.0

# --- Colours (validated categorical slots 1-2, one-hue blue ramp, neutral inks) ---------------------------
WATER, SHORTAGE = "#2a78d6", "#eb6834"
INK, SECONDARY, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#fcfcfb"
BLUE_RAMP = LinearSegmentedColormap.from_list("blue_ramp", ["#cde2fb", "#6da7ec", "#256abf", "#0d366b"])

_EXPLORER_DIR = Path(__file__).parent / "rationing_explorer"


@dataclass(frozen=True)
class Plan:
    """A rationing plan: below `trigger` Mm³ in the reservoir, deliver only `ration` of the summer need."""

    trigger: float = 0.0
    ration: float = 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.trigger <= CAPACITY_MM3:
            raise ValueError(f"trigger must be between 0 and {CAPACITY_MM3:g} Mm³, got {self.trigger}")
        if not 0.0 <= self.ration <= 1.0:
            raise ValueError(f"ration must be between 0 and 1, got {self.ration}")


NO_RATIONING = Plan()


@dataclass(frozen=True)
class Scores:
    """How a plan did: the water not delivered on average, how bad the worst month was, and how often it was short."""

    mean_shortage: float  # Mm³ per year
    worst_month: float  # % of that month's need not delivered
    years_short: int  # years with at least one short month


@dataclass(frozen=True)
class RunResult:
    plan: Plan
    scores: Scores
    storage: np.ndarray  # Mm³ at the end of each month
    shortage_by_month: np.ndarray  # % of that month's need not delivered

    @property
    def worst_month_by_year(self) -> np.ndarray:
        """The shortage of the worst month of each year, in percent of that month's need."""
        return self.shortage_by_month.reshape(-1, 12).max(axis=1)


# --- The river ----------------------------------------------------------------------------------------------


def _lognormal_parameters(mean: float, sd: float) -> tuple[float, float]:
    variance = np.log(1.0 + (sd / mean) ** 2)
    return float(np.log(mean) - variance / 2.0), float(np.sqrt(variance))


def _season_totals(years: int, seed: int, regime: Regime) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    winter_mu, winter_sigma = _lognormal_parameters(*regime.winter)
    summer_mu, summer_sigma = _lognormal_parameters(*regime.summer)
    winter, summer, z_summer = np.empty(years), np.empty(years), 0.0
    for year in range(years):
        z_winter = (
            SUMMER_TO_WINTER_CORRELATION * z_summer
            + np.sqrt(1.0 - SUMMER_TO_WINTER_CORRELATION**2) * rng.standard_normal()
        )
        z_summer = (
            WINTER_TO_SUMMER_CORRELATION * z_winter
            + np.sqrt(1.0 - WINTER_TO_SUMMER_CORRELATION**2) * rng.standard_normal()
        )
        winter[year] = np.exp(winter_mu + winter_sigma * z_winter)
        summer[year] = np.exp(summer_mu + summer_sigma * z_summer)
    return winter, summer


def synthetic_inflows(years: int = YEARS, seed: int = SEED, regime: Regime = DEFAULT_REGIME) -> tuple[float, ...]:
    """Generate a synthetic river with the given seasonal statistics.

    Each year has a winter and a summer total drawn from log-normal distributions; a dry season tends to follow
    a dry season. Each season's total is spread evenly over its six months.

    Args:
        years: Number of years to generate.
        seed: Seed of the random number generator.
        regime: The seasonal pattern (`CENTRAL_ASIA_REGIME` by default, or `PAPER_REGIME`).

    Returns:
        Monthly inflow in Mm³, winter months first, `12 * years` values.

    Raises:
        ValueError: If `years` is less than one.
    """
    if years < 1:
        raise ValueError(f"need at least one year, got {years}")
    winter, summer = _season_totals(years, seed, regime)
    monthly = np.repeat(np.column_stack([winter, summer]) / MONTHS_PER_SEASON, MONTHS_PER_SEASON, axis=1)
    return tuple(float(value) for value in monthly.ravel())


def season_totals(inflows: tuple[float, ...]) -> tuple[np.ndarray, np.ndarray]:
    """Winter and summer inflow totals per year, in Mm³."""
    by_year = np.asarray(inflows).reshape(-1, 12)
    return by_year[:, :MONTHS_PER_SEASON].sum(axis=1), by_year[:, MONTHS_PER_SEASON:].sum(axis=1)


def season_statistics(inflows: tuple[float, ...], regime: Regime = DEFAULT_REGIME) -> pd.DataFrame:
    """Compare the river's seasonal statistics with the regime it was drawn from."""
    winter, summer = season_totals(inflows)
    rows = [
        ("Winter inflow, mean (Mm³)", regime.winter[0], winter.mean()),
        ("Winter inflow, standard deviation (Mm³)", regime.winter[1], winter.std(ddof=1)),
        ("Summer inflow, mean (Mm³)", regime.summer[0], summer.mean()),
        ("Summer inflow, standard deviation (Mm³)", regime.summer[1], summer.std(ddof=1)),
        ("Link winter → next summer (correlation)", WINTER_TO_SUMMER_CORRELATION, np.corrcoef(winter, summer)[0, 1]),
        (
            "Link summer → next winter (correlation)",
            SUMMER_TO_WINTER_CORRELATION,
            np.corrcoef(summer[:-1], winter[1:])[0, 1],
        ),
    ]
    return pd.DataFrame(rows, columns=["statistic", "target", "this river"]).round(2)


# --- The building blocks ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class RationingRelease(Strategy):
    """Release what the farm needs.

    In summer, when the reservoir holds less than the trigger, release only the ration of it.
    """

    __params__: ClassVar[tuple[str, ...]] = ("trigger", "ration")
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {
        "trigger": (0.0, CAPACITY_MM3),
        "ration": (0.0, 1.0),
    }

    trigger: float = 0.0
    ration: float = 1.0

    def release(self, node: Storage, inflow: float, t: Timestep) -> float:
        month = t.index % 12  # 0-5 = winter, 6-11 = summer
        need = MONTHLY_NEED_MM3[month]  # what the farm asks for this month, Mm³
        if month in SUMMER_MONTHS and node.storage < self.trigger:
            need *= self.ration  # rationing: deliver only this share of the need
        return min(need, node.storage)  # never release more than is in the reservoir


@dataclass(frozen=True)
class SummerEvaporation:
    """Each summer month a fixed share of the stored water evaporates."""

    share: float

    def calculate(self, node: Storage, t: Timestep) -> dict:
        if t.index % 12 not in SUMMER_MONTHS:
            return {}  # no loss in winter
        return {EVAPORATION: self.share * node.storage}  # Mm³ lost this month, booked as evaporation


def build_system(
    inflows: tuple[float, ...],
    plan: Plan = NO_RATIONING,
    evaporation_share: float = 0.0,
    start_storage: float = START_STORAGE_MM3,
) -> WaterSystem:
    """Build the four-block system: river → reservoir → farm → downstream.

    Args:
        inflows: Monthly river inflow in Mm³.
        plan: The rationing plan the reservoir follows.
        evaporation_share: Share of the stored water lost per summer month (0 = no evaporation).
        start_storage: Water in the reservoir at the start, in Mm³.

    Returns:
        A validated system, not yet simulated.
    """
    years = len(inflows) // 12
    system = WaterSystem(frequency=Frequency.MONTHLY)
    system.add_node(Source(id="river", inflow=TimeSeries(values=list(inflows))))
    system.add_node(
        Storage(
            id="reservoir",
            capacity=CAPACITY_MM3,
            initial_storage=start_storage,
            release_policy=RationingRelease(trigger=plan.trigger, ration=plan.ration),
            loss_rule=SummerEvaporation(share=evaporation_share) if evaporation_share > 0.0 else NoLoss(),
        )
    )
    system.add_node(Demand(id="farm", requirement=TimeSeries(values=list(MONTHLY_NEED_MM3) * years)))
    system.add_node(Sink(id="downstream"))
    for source, target in (("river", "reservoir"), ("reservoir", "farm"), ("farm", "downstream")):
        system.add_edge(Edge(id=f"{source}_to_{target}", source=source, target=target))
    system.validate()
    return system


# --- Reading a run ------------------------------------------------------------------------------------------


def _monthly(node, event_type: type, field: str = "amount") -> np.ndarray:
    totals: dict[int, float] = {}
    for event in node.events_of_type(event_type):
        totals[event.t] = totals.get(event.t, 0.0) + getattr(event, field)
    steps = max(totals, default=-1) + 1
    return np.array([totals.get(t, 0.0) for t in range(steps)])


def _padded(values: np.ndarray, steps: int) -> np.ndarray:
    return np.pad(values, (0, steps - len(values)))


def shortage_by_month(system: WaterSystem) -> np.ndarray:
    """Share of each month's need the farm did not get, in percent."""
    steps = len(system.nodes["river"].inflow.values)
    deficit = _padded(_monthly(system.nodes["farm"], DeficitRecorded, "deficit"), steps)
    return deficit / np.tile(MONTHLY_NEED_MM3, steps // 12) * 100.0


def _scores(shortage: np.ndarray) -> Scores:
    by_year = shortage.reshape(-1, 12)
    volume = by_year / 100.0 * np.asarray(MONTHLY_NEED_MM3)
    return Scores(
        mean_shortage=float(volume.sum() / len(by_year)),
        worst_month=float(shortage.max()),
        years_short=int((by_year.max(axis=1) > SHORT_TOLERANCE_PERCENT).sum()),
    )


def _storage_path(system: WaterSystem) -> np.ndarray:
    reservoir = system.nodes["reservoir"]
    steps = len(system.nodes["river"].inflow.values)
    change = (
        _padded(_monthly(reservoir, WaterStored), steps)
        - _padded(_monthly(reservoir, WaterLost), steps)
        - _padded(_monthly(reservoir, WaterReleased), steps)
    )
    return reservoir.initial_storage + np.cumsum(change)


def drought_window_start(run: RunResult, window_years: int = 20) -> int:
    """The first year (1-based) of a window of `window_years` years that contains the run's worst month."""
    years = len(run.worst_month_by_year)
    worst = int(run.worst_month_by_year.argmax())
    return int(np.clip(worst - window_years * 3 // 5, 0, years - window_years)) + 1


def simulate_plan(
    inflows: tuple[float, ...],
    plan: Plan,
    evaporation_share: float = 0.0,
    start_storage: float = START_STORAGE_MM3,
) -> RunResult:
    """Run one plan through TaqSim and read off storage, monthly shortages and scores."""
    system = build_system(inflows, plan, evaporation_share=evaporation_share, start_storage=start_storage)
    system.simulate(len(inflows))
    shortage = shortage_by_month(system)
    return RunResult(plan=plan, scores=_scores(shortage), storage=_storage_path(system), shortage_by_month=shortage)


def objectives() -> list[Objective]:
    """The two goals the optimizer weighs: little water not delivered, and a mild worst month."""
    # Each goal is a function of the simulated system that returns one number to make as small as possible.
    return [
        Objective(
            name="mean_shortage",  # Mm³ per year the farm did not get
            direction="minimize",
            evaluate=lambda system: _scores(shortage_by_month(system)).mean_shortage,
        ),
        Objective(
            name="worst_month",  # % of its need the farm did not get in the worst month
            direction="minimize",
            evaluate=lambda system: _scores(shortage_by_month(system)).worst_month,
        ),
    ]


# --- Many plans ---------------------------------------------------------------------------------------------


GOALS = ("mean_shortage", "worst_month")


def plan_grid(n_trigger: int = 21, n_ration: int = 21) -> list[Plan]:
    """Evenly spaced plans covering every trigger (0 to capacity) and every ration (0 to 1)."""
    return [
        Plan(trigger=float(trigger), ration=float(ration))
        for trigger in np.linspace(0.0, CAPACITY_MM3, n_trigger)
        for ration in np.linspace(0.0, 1.0, n_ration)
    ]


def unbeaten(points: np.ndarray) -> np.ndarray:
    """Mark the rows no other row beats (lower is better in every column).

    A row is beaten when another row is at least as good in every column and better in at least one.
    """
    points = np.asarray(points, dtype=float)
    at_least_as_good = np.all(points[None, :, :] <= points[:, None, :], axis=2)
    better_somewhere = np.any(points[None, :, :] < points[:, None, :], axis=2)
    return ~np.any(at_least_as_good & better_somewhere, axis=1)


def _score_table(inflows: tuple[float, ...], plans: list[Plan], evaporation_share: float) -> pd.DataFrame:
    rows = []
    for plan in plans:
        scores = simulate_plan(inflows, plan, evaporation_share=evaporation_share).scores
        rows.append((plan.trigger, plan.ration, scores.mean_shortage, scores.worst_month, scores.years_short))
    table = pd.DataFrame(rows, columns=["trigger", "ration", "mean_shortage", "worst_month", "years_short"])
    table["unbeaten"] = unbeaten(table[list(GOALS)].to_numpy().round(6))
    return table


def score_plans(inflows: tuple[float, ...], plans: list[Plan], evaporation_share: float = 0.0) -> pd.DataFrame:
    """Run every plan and tabulate its scores.

    Returns:
        One row per plan with `trigger`, `ration`, `mean_shortage`, `worst_month`, `years_short` and `unbeaten`
        (no other plan in the table has both a smaller average shortage and a milder worst month).
    """
    return _score_table(inflows, plans, evaporation_share)


def optimise_plans(
    inflows: tuple[float, ...],
    pop_size: int = 40,
    generations: int = 40,
    seed: int = 42,
    evaporation_share: float = 0.0,
) -> pd.DataFrame:
    """Let NSGA-II (`taqsim.optimize`) search the two knobs for plans that are not beaten.

    Returns:
        The plans the optimizer returns, scored like `score_plans`, sorted by `mean_shortage`.
    """
    result = optimize(
        system=build_system(inflows, evaporation_share=evaporation_share),
        objectives=objectives(),
        timesteps=len(inflows),
        pop_size=pop_size,
        generations=generations,
        seed=seed,
    )
    plans = [
        Plan(
            trigger=float(np.clip(_parameter(solution.parameters, "trigger"), 0.0, CAPACITY_MM3)),
            ration=float(np.clip(_parameter(solution.parameters, "ration"), 0.0, 1.0)),
        )
        for solution in result
    ]
    logger.info("optimizer returned %d plans", len(plans))
    table = _score_table(inflows, plans, evaporation_share)
    return table.sort_values(list(GOALS)).reset_index(drop=True)


def _parameter(parameters: dict[str, float], name: str) -> float:
    return next(value for path, value in parameters.items() if path.endswith(name))


def front_of(table: pd.DataFrame) -> pd.DataFrame:
    """The distinct unbeaten (average shortage, worst month) pairs of a score table, smallest shortage first."""
    # Plans with the same scores are listed once, by the one that rations least (e.g. "no rationing" as ration 1).
    ties_first = table[table["unbeaten"]].sort_values(["ration", "trigger"], ascending=[False, True])
    front = ties_first.round({"mean_shortage": 6, "worst_month": 6}).drop_duplicates(list(GOALS))
    return front.sort_values("mean_shortage").reset_index(drop=True)


# --- The explorer on the web page ---------------------------------------------------------------------------


def explorer_payload(inflows: tuple[float, ...], table: pd.DataFrame, window_years: int = 20) -> dict:
    """Collect what the page's explorer shows: every plan's TaqSim scores, each year's worst month, and storage.

    Storage is given for a window of `window_years` years around the worst year without rationing.
    """
    years = len(inflows) // 12
    start = drought_window_start(simulate_plan(inflows, NO_RATIONING), window_years) - 1
    plans = []
    for row in table.itertuples():
        run = simulate_plan(inflows, Plan(trigger=row.trigger, ration=row.ration))
        plans.append(
            {
                "trigger": round(row.trigger, 3),
                "ration": round(row.ration, 3),
                "mean_shortage": round(row.mean_shortage, 2),
                "worst_month": round(row.worst_month, 1),
                "years_short": int(row.years_short),
                "unbeaten": bool(row.unbeaten),
                "shortage": [round(float(value), 1) for value in run.worst_month_by_year],
                "storage": [round(float(value), 1) for value in run.storage[12 * start : 12 * (start + window_years)]],
            }
        )
    return {
        "capacity": CAPACITY_MM3,
        "years": years,
        "mean_axis_max": MEAN_SHORTAGE_AXIS_MAX,
        "window": {"start_year": start + 1, "years": window_years},
        "plans": plans,
    }


def explorer_html(payload: dict, compact: bool = False) -> str:
    """The explorer as one HTML fragment: styles, markup, the data as JSON, and the script that draws it.

    Args:
        payload: From `explorer_payload`.
        compact: Shorter charts and tighter spacing, for a slide.
    """
    data = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
    markup = (_EXPLORER_DIR / "explorer.html").read_text(encoding="utf-8")
    if compact:
        markup = markup.replace('id="rationing-explorer"', 'id="rationing-explorer" data-compact="1"', 1)
    return "\n".join(
        [
            f"<style>{(_EXPLORER_DIR / 'explorer.css').read_text(encoding='utf-8')}</style>",
            markup,
            f'<script type="application/json" id="rationing-data">{data}</script>',
            f"<script>{(_EXPLORER_DIR / 'explorer.js').read_text(encoding='utf-8')}</script>",
        ]
    )


# --- Figures ------------------------------------------------------------------------------------------------


def _style(ax: plt.Axes) -> None:
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.xaxis.label.set_color(SECONDARY)
    ax.yaxis.label.set_color(SECONDARY)
    ax.xaxis.label.set_size(9)
    ax.yaxis.label.set_size(9)


NETWORK_NODES: tuple[tuple[str, str, str], ...] = (
    ("river", "Source", "inflow from a time series"),
    ("reservoir", "Storage", "stores, loses and releases water"),
    ("farm", "Demand", "asks for water, records deficits"),
    ("downstream", "Sink", "takes what is left"),
)
NETWORK_EDGES: tuple[tuple[str, str], ...] = (("river", "reservoir"), ("reservoir", "farm"), ("farm", "downstream"))
_NODE_MARKERS = {"Source": "o", "Storage": "s", "Demand": "h", "Sink": "v"}


def plot_network() -> Figure:
    """The model as TaqSim sees it: four nodes joined by three edges, water flowing left to right."""
    fig, ax = plt.subplots(figsize=(8.0, 2.4))
    positions = {node_id: (i * 2.4, 0.0) for i, (node_id, _, _) in enumerate(NETWORK_NODES)}
    for source, target in NETWORK_EDGES:
        (x0, y0), (x1, y1) = positions[source], positions[target]
        ax.annotate(
            "",
            xy=(x1 - 0.55, y1),
            xytext=(x0 + 0.55, y0),
            arrowprops={"arrowstyle": "-|>", "color": WATER, "linewidth": 1.8, "shrinkA": 0, "shrinkB": 0},
        )
        ax.text((x0 + x1) / 2, 0.2, f"{source}_to_{target}", ha="center", fontsize=7, color=MUTED, family="monospace")
    for node_id, kind, note in NETWORK_NODES:
        x, y = positions[node_id]
        ax.scatter(x, y, s=3000, marker=_NODE_MARKERS[kind], color=SURFACE, edgecolors=INK, linewidths=1.4, zorder=3)
        label_y = y + 0.08 if kind == "Sink" else y  # a triangle's visual centre sits above its middle
        ax.text(x, label_y, node_id, ha="center", va="center", fontsize=8, color=INK, weight="bold", zorder=4)
        ax.text(x, -0.62, kind, ha="center", va="top", fontsize=8.5, color=SECONDARY)
        ax.text(x, -0.85, note, ha="center", va="top", fontsize=7.5, color=MUTED)
    ax.set_xlim(-0.9, positions["downstream"][0] + 0.9)
    ax.set_ylim(-1.2, 0.55)
    ax.axis("off")
    fig.tight_layout()
    return fig


def plot_system_sketch(regime: Regime = DEFAULT_REGIME) -> Figure:
    """The four blocks and what moves between them."""
    fig, ax = plt.subplots(figsize=(8.0, 1.9))
    blocks = [
        ("River", f"winter {regime.winter[0]:g}, summer {regime.summer[0]:g}\nMm³ on average", "Source"),
        ("Reservoir", f"holds up to {CAPACITY_MM3:g} Mm³\ntwo knobs: trigger, ration", "Storage"),
        ("Farm", f"needs {SUMMER_NEED_MM3:g} Mm³ in summer\n{WINTER_NEED_MM3:g} Mm³ in winter", "Demand"),
        ("Downstream", "takes what is left", "Sink"),
    ]
    width, gap = 2.0, 0.55
    for i, (name, note, kind) in enumerate(blocks):
        x = i * (width + gap)
        ax.add_patch(plt.Rectangle((x, 0.0), width, 1.0, facecolor=SURFACE, edgecolor=SECONDARY, linewidth=1.0))
        ax.text(x + width / 2, 0.74, name, ha="center", va="center", fontsize=10, color=INK, weight="bold")
        ax.text(x + width / 2, 0.36, note, ha="center", va="center", fontsize=8, color=SECONDARY)
        ax.text(x + width / 2, -0.16, f"TaqSim block: {kind}", ha="center", va="center", fontsize=7.5, color=MUTED)
        if i < len(blocks) - 1:
            ax.annotate(
                "",
                xy=(x + width + gap, 0.5),
                xytext=(x + width, 0.5),
                arrowprops={"arrowstyle": "-|>", "color": WATER, "linewidth": 2.0},
            )
    ax.set_xlim(-0.1, len(blocks) * (width + gap) - gap + 0.1)
    ax.set_ylim(-0.35, 1.1)
    ax.axis("off")
    fig.tight_layout()
    return fig


def plot_inflows(inflows: tuple[float, ...]) -> Figure:
    """Winter and summer inflow of every year, against the reservoir size and the summer need."""
    winter, summer = season_totals(inflows)
    years = np.arange(1, len(winter) + 1)
    fig, ax = plt.subplots(figsize=(8.0, 3.0))
    ax.plot(years, winter, color=WATER, linewidth=1.6)
    ax.plot(years, summer, color=SHORTAGE, linewidth=1.6)
    ax.axhline(SUMMER_NEED_MM3, color=MUTED, linewidth=1.0)
    ax.text(len(years) + 1.5, winter[-1], "winter inflow", color=SECONDARY, fontsize=8, va="center")
    ax.text(len(years) + 1.5, summer[-1], "summer inflow", color=SECONDARY, fontsize=8, va="center")
    ax.text(1, SUMMER_NEED_MM3 + 1.5, f"summer need of the farm, {SUMMER_NEED_MM3:g} Mm³", color=MUTED, fontsize=8)
    ax.set_xlim(0, len(years) + 16)
    ax.set_ylim(0, None)
    ax.set_xlabel("Year")
    ax.set_ylabel("Inflow (Mm³ per season)")
    _style(ax)
    fig.tight_layout()
    return fig


def plot_runs(runs: dict[str, RunResult], first_year: int = 1, window_years: int = 20) -> Figure:
    """One row per plan: each year's worst month over all years (left, the shown window shaded) and storage over
    a window of years (right)."""
    fig, axes = plt.subplots(
        len(runs), 2, figsize=(8.0, 2.1 * len(runs) + 0.4), sharex="col", sharey="col", squeeze=False
    )
    for (label, run), (left, right) in zip(runs.items(), axes, strict=True):
        worst = run.worst_month_by_year
        left.axvspan(first_year - 0.5, first_year + window_years - 0.5, color=WATER, alpha=0.12, linewidth=0)
        left.bar(np.arange(1, len(worst) + 1), worst, width=0.7, color=SHORTAGE)
        left.set_ylim(0, 100)
        left.set_ylabel("Worst month of the year\n(% of its need not delivered)")
        left.set_title(label, loc="left", fontsize=9.5, color=INK, weight="bold")
        months = np.arange(12 * (first_year - 1), 12 * (first_year - 1 + window_years))
        right.plot(months / 12 + 1, run.storage[months], color=WATER, linewidth=1.4)
        if run.plan.trigger > 0.0 and run.plan.ration < 1.0:
            right.axhline(run.plan.trigger, color=MUTED, linewidth=1.0)
            right.text(first_year + 0.1, run.plan.trigger + 1.0, "trigger", color=MUTED, fontsize=7.5)
        right.xaxis.set_major_locator(MaxNLocator(integer=True))
        right.set_ylim(0, CAPACITY_MM3 * 1.05)
        right.set_ylabel("Storage (Mm³)")
        scores = run.scores
        right.set_title(
            f"{scores.mean_shortage:.1f} Mm³/yr short · worst month {scores.worst_month:.0f} % · "
            f"{scores.years_short} years short",
            loc="left",
            fontsize=8.5,
            color=SECONDARY,
        )
        _style(left)
        _style(right)
    axes[-1][0].set_xlabel("Year (all years; shaded: the years shown on the right)")
    axes[-1][1].set_xlabel(f"Year (a window of {window_years} years)")
    fig.tight_layout()
    return fig


def plot_score_maps(table: pd.DataFrame) -> Figure:
    """Each score for every plan: trigger across, ration up, darker = worse."""
    columns = [
        ("mean_shortage", "Average shortage (Mm³/yr)"),
        ("worst_month", "Worst month (% short)"),
        ("years_short", "Years short (of 100)"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(9.0, 3.1), sharey=True)
    triggers, rations = np.sort(table["trigger"].unique()), np.sort(table["ration"].unique())
    for ax, (column, title) in zip(axes, columns, strict=True):
        values = table.pivot(index="ration", columns="trigger", values=column).to_numpy()
        mesh = ax.pcolormesh(triggers, rations * 100, values, cmap=BLUE_RAMP, shading="nearest")
        colorbar = fig.colorbar(mesh, ax=ax, fraction=0.05, pad=0.03)
        colorbar.ax.tick_params(labelsize=7, colors=MUTED)
        colorbar.outline.set_visible(False)
        ax.set_title(title, loc="left", fontsize=9, color=INK)
        ax.set_xlabel("Trigger (Mm³ in store)")
        _style(ax)
        ax.grid(False)
    axes[0].set_ylabel("Ration (% of need delivered)")
    fig.tight_layout()
    return fig


def plot_tradeoff(
    table: pd.DataFrame,
    found: pd.DataFrame | None = None,
    named: dict[str, RunResult] | None = None,
) -> Figure:
    """Every plan as a dot: water not delivered on average (across) against the worst month (up).

    Args:
        table: Scores of the grid plans, from `score_plans`.
        found: Plans the optimizer returned, drawn on top.
        named: Runs to label by name.
    """
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    beaten = table[~table["unbeaten"]]
    front = front_of(table)
    ax.scatter(beaten["mean_shortage"], beaten["worst_month"], s=14, color="#c3c2b7", linewidths=0, label="beaten plan")
    ax.plot(front["mean_shortage"], front["worst_month"], color=INK, linewidth=1.0, drawstyle="steps-post", zorder=2)
    ax.scatter(
        front["mean_shortage"],
        front["worst_month"],
        s=34,
        color=INK,
        edgecolors=SURFACE,
        linewidths=1.2,
        zorder=3,
        label="unbeaten plan (grid)",
    )
    if found is not None:
        ax.scatter(
            found["mean_shortage"],
            found["worst_month"],
            s=30,
            color=WATER,
            edgecolors=SURFACE,
            linewidths=1.0,
            zorder=4,
            label="found by the optimizer",
        )
    # Labels alternate between above and right of their point, so that neighbours do not sit on each other.
    offsets = ((-6, 13), (13, -3))
    for i, (label, run) in enumerate((named or {}).items()):
        point = (run.scores.mean_shortage, run.scores.worst_month)
        ax.scatter(*point, s=90, facecolors="none", edgecolors=SHORTAGE, linewidths=2.0, zorder=5)
        ax.annotate(label, point, xytext=offsets[i % 2], textcoords="offset points", fontsize=8.5, color=INK)
    beyond = int((table["mean_shortage"] > MEAN_SHORTAGE_AXIS_MAX).sum())
    if beyond:
        ax.text(
            0.99,
            0.03,
            f"{beyond} plans lie further right →",
            transform=ax.transAxes,
            ha="right",
            fontsize=8,
            color=MUTED,
        )
    ax.set_xlabel("Average shortage (Mm³ per year) — less is better")
    ax.set_ylabel("Worst month (% of need not delivered) — lower is better")
    ax.set_xlim(0, MEAN_SHORTAGE_AXIS_MAX)
    ax.set_ylim(0, 100)
    ax.legend(frameon=False, fontsize=8, labelcolor=SECONDARY, loc="upper right")
    _style(ax)
    fig.tight_layout()
    return fig


def plot_front_shift(fronts: dict[str, pd.DataFrame]) -> Figure:
    """Compare the unbeaten plans of two or more score tables (e.g. without and with evaporation)."""
    fig, ax = plt.subplots(figsize=(7.0, 3.8))
    for (label, table), color in zip(fronts.items(), (WATER, SHORTAGE, "#1baf7a"), strict=False):
        front = front_of(table)
        front = front[front["mean_shortage"] <= MEAN_SHORTAGE_AXIS_MAX]
        ax.plot(
            front["mean_shortage"],
            front["worst_month"],
            color=color,
            linewidth=1.6,
            drawstyle="steps-post",
            marker="o",
            markersize=5,
            markeredgecolor=SURFACE,
            label=label,
        )
    ax.set_xlabel("Average shortage (Mm³ per year) — less is better")
    ax.set_ylabel("Worst month (% short) — lower is better")
    ax.set_xlim(0, MEAN_SHORTAGE_AXIS_MAX)
    ax.set_ylim(0, 100)
    ax.legend(frameon=False, fontsize=8.5, labelcolor=SECONDARY, loc="upper right")
    _style(ax)
    fig.tight_layout()
    return fig


def plot_regime_comparison(cases: dict[str, tuple[tuple[float, ...], pd.DataFrame]]) -> Figure:
    """Two or three rivers side by side: their average month (left) and their unbeaten plans (right).

    Args:
        cases: Label -> (inflows, score table of the grid plans on those inflows).
    """
    fig, (left, right) = plt.subplots(1, 2, figsize=(11.0, 4.2))
    colors = (WATER, SHORTAGE, "#1baf7a")
    width = 0.8 / len(cases)
    for i, ((label, (inflows, table)), color) in enumerate(zip(cases.items(), colors, strict=False)):
        monthly_mean = np.asarray(inflows).reshape(-1, 12).mean(axis=0)
        shift = (i - (len(cases) - 1) / 2) * width
        left.bar(np.arange(12) + shift, monthly_mean, width=width * 0.95, color=color, label=label)
        front = front_of(table)
        front = front[front["mean_shortage"] <= MEAN_SHORTAGE_AXIS_MAX]
        right.plot(
            front["mean_shortage"],
            front["worst_month"],
            color=color,
            linewidth=1.6,
            drawstyle="steps-post",
            marker="o",
            markersize=5,
            markeredgecolor=SURFACE,
            label=label,
        )
        first = front.iloc[0]
        right.annotate(
            "no rationing",
            (first["mean_shortage"], first["worst_month"]),
            xytext=(8, 4),
            textcoords="offset points",
            fontsize=8,
            color=SECONDARY,
        )
    need = list(MONTHLY_NEED_MM3) + [MONTHLY_NEED_MM3[-1]]
    left.step(np.arange(-0.5, 12.5), need, where="post", color=INK, linewidth=1.2)
    left.text(6.1, MONTHLY_NEED_MM3[-1] + 0.25, "farm need", fontsize=8.5, color=INK)
    left.set_xticks(np.arange(12), [f"W{i}" for i in range(1, 7)] + [f"S{i}" for i in range(1, 7)])
    left.set_xlabel("Month of the year (W = winter, S = summer)")
    left.set_ylabel("Average inflow (Mm³ per month)")
    left.set_title("Same water per year, different timing", loc="left", fontsize=10, color=INK)
    right.set_xlim(0, MEAN_SHORTAGE_AXIS_MAX)
    right.set_ylim(0, 100)
    right.set_xlabel("Average shortage (Mm³ per year) — less is better")
    right.set_ylabel("Worst month (% short) — lower is better")
    right.set_title("The unbeaten plans", loc="left", fontsize=10, color=INK)
    for ax in (left, right):
        ax.legend(frameon=False, fontsize=8.5, labelcolor=SECONDARY)
        _style(ax)
    fig.tight_layout()
    return fig
