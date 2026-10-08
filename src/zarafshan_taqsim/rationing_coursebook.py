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
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

import matplotlib as mpl
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
# --- The winter fields (the "one more user" sections). Illustrative, like the evaporation share.
WINTER_MONTHS = range(0, MONTHS_PER_SEASON)
# What the winter fields (winter wheat, salt leaching) ask for in each winter month, Mm³; nothing in summer
WINTER_FIELDS_NEED_MM3: tuple[float, ...] = (2.5,) * MONTHS_PER_SEASON + (0.0,) * MONTHS_PER_SEASON
WINTER_FIELDS_TOTAL_MM3 = sum(WINTER_FIELDS_NEED_MM3)
# The winter trigger is compared with the "water in sight": the storage plus, if there is one, the forecast of
# the coming summer. Its scale is therefore the reservoir plus a large summer.
WINTER_TRIGGER_MAX_MM3 = 120.0
FORECAST_SEED = SEED + 1  # the forecaster's noise; a different seed from the river's
# The trade-off charts stop here on the average-shortage axis; plans beyond it are far from any sensible choice.
MEAN_SHORTAGE_AXIS_MAX = 12.0

# --- Colours (validated categorical slots 1-2, one-hue blue ramp, neutral inks) ---------------------------
WATER, SHORTAGE = "#2a78d6", "#d95926"
INK, SECONDARY, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#6b6a66", "#e1e0d9", "#fcfcfb"
AXIS, REFERENCE, GREEN = "#b8b7ae", "#c3c2b7", "#1baf7a"
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
# The summer plan kept fixed in the winter sections: "cut deep" from the second run
SUMMER_PLAN_FOR_WINTER = Plan(trigger=16.0, ration=0.5)


@dataclass(frozen=True)
class WinterPlan:
    """A winter plan: when the water in sight is below `trigger` Mm³, deliver only `ration` of the winter need.

    The water in sight is the storage, plus the forecast of the coming summer when the operator has one.
    """

    trigger: float = 0.0
    ration: float = 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.trigger <= WINTER_TRIGGER_MAX_MM3:
            raise ValueError(f"winter trigger must be between 0 and {WINTER_TRIGGER_MAX_MM3:g} Mm³, got {self.trigger}")
        if not 0.0 <= self.ration <= 1.0:
            raise ValueError(f"winter ration must be between 0 and 1, got {self.ration}")


WINTER_IN_FULL = WinterPlan()


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


def seasonal_forecast(
    inflows: tuple[float, ...], skill: float, seed: int = FORECAST_SEED, regime: Regime = DEFAULT_REGIME
) -> tuple[float, ...]:
    """A forecast of each summer's inflow, one number per year, with the given skill.

    The forecaster sees the coming summer through noise: `skill` is the correlation between what it sees and
    the truth. The forecast is the best guess given what it sees, so with skill 0 it is the long-run average
    summer and with skill 1 it is the summer itself.

    Args:
        inflows: Monthly river inflow in Mm³, as from `synthetic_inflows`.
        skill: Correlation between the forecast and the truth, 0 (no skill) to 1 (perfect).
        seed: Seed of the forecaster's noise.
        regime: The seasonal pattern the inflows were drawn from.

    Returns:
        Forecast summer inflow in Mm³, one value per year.

    Raises:
        ValueError: If `skill` is outside 0 to 1.
    """
    if not 0.0 <= skill <= 1.0:
        raise ValueError(f"skill must be between 0 and 1, got {skill}")
    _, summer = season_totals(inflows)
    mu, sigma = _lognormal_parameters(*regime.summer)
    truth = (np.log(summer) - mu) / sigma  # the summer, as a standard score
    rng = np.random.default_rng(seed)
    seen = skill * truth + np.sqrt(1.0 - skill**2) * rng.standard_normal(len(summer))  # the truth through noise
    # The best guess of the summer given what was seen: the mean of a log-normal, narrowed by the forecaster's skill
    guess = np.exp(mu + sigma * skill * seen + sigma**2 * (1.0 - skill**2) / 2.0)
    return tuple(float(value) for value in guess)


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
class WinterRelease(Strategy):
    """The summer rule with its two knobs, plus two knobs for winter.

    In winter, deliver what the winter fields ask for, unless the water in sight (the storage, plus the forecast
    of the coming summer if there is one) is below the winter trigger: then deliver only the winter ration of it.
    """

    __params__: ClassVar[tuple[str, ...]] = ("trigger", "ration", "winter_trigger", "winter_ration")
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {
        "trigger": (0.0, CAPACITY_MM3),
        "ration": (0.0, 1.0),
        "winter_trigger": (0.0, WINTER_TRIGGER_MAX_MM3),
        "winter_ration": (0.0, 1.0),
    }

    trigger: float = 0.0
    ration: float = 1.0
    winter_trigger: float = 0.0
    winter_ration: float = 1.0
    forecast: tuple[float, ...] = field(default=(), compare=False)  # one forecast per year, Mm³; empty: none

    def release(self, node: Storage, inflow: float, t: Timestep) -> float:
        month = t.index % 12
        need = MONTHLY_NEED_MM3[month]  # what the farm asks for this month
        if month in SUMMER_MONTHS:
            if node.storage < self.trigger:
                need *= self.ration
            return min(need, node.storage)
        in_sight = node.storage + (self.forecast[t.index // 12] if self.forecast else 0.0)
        winter_need = WINTER_FIELDS_NEED_MM3[month]  # what the winter fields ask for
        if in_sight < self.winter_trigger:
            winter_need *= self.winter_ration
        return min(need + winter_need, node.storage)


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
    winter: WinterPlan | None = None,
    forecast: tuple[float, ...] | None = None,
) -> WaterSystem:
    """Build the four-block system river → reservoir → farm → downstream, or, with a winter plan, the five-block
    system with the winter fields between the farm and the sink.

    Args:
        inflows: Monthly river inflow in Mm³.
        plan: The rationing plan the reservoir follows in summer.
        evaporation_share: Share of the stored water lost per summer month (0 = no evaporation).
        start_storage: Water in the reservoir at the start, in Mm³.
        winter: The winter plan; None builds the four-block system without the winter fields.
        forecast: One forecast of the summer inflow per year, Mm³, as from `seasonal_forecast`; None means the
            winter plan looks at the storage alone. Only used with a winter plan.

    Returns:
        A validated system, not yet simulated.

    Raises:
        ValueError: If the forecast does not have one value per year.
    """
    years = len(inflows) // 12
    if winter is None:
        policy: Strategy = RationingRelease(trigger=plan.trigger, ration=plan.ration)
    else:
        if forecast is not None and len(forecast) != years:
            raise ValueError(f"the forecast needs one value per year ({years}), got {len(forecast)}")
        policy = WinterRelease(
            trigger=plan.trigger,
            ration=plan.ration,
            winter_trigger=winter.trigger,
            winter_ration=winter.ration,
            forecast=tuple(forecast or ()),
        )
    system = WaterSystem(frequency=Frequency.MONTHLY)
    system.add_node(Source(id="river", inflow=TimeSeries(values=list(inflows))))
    system.add_node(
        Storage(
            id="reservoir",
            capacity=CAPACITY_MM3,
            initial_storage=start_storage,
            release_policy=policy,
            loss_rule=SummerEvaporation(share=evaporation_share) if evaporation_share > 0.0 else NoLoss(),
        )
    )
    system.add_node(Demand(id="farm", requirement=TimeSeries(values=list(MONTHLY_NEED_MM3) * years)))
    chain = ["river", "reservoir", "farm", "downstream"]
    if winter is not None:
        system.add_node(Demand(id="winter_fields", requirement=TimeSeries(values=list(WINTER_FIELDS_NEED_MM3) * years)))
        chain.insert(3, "winter_fields")  # the winter fields take what the farm passes on
    system.add_node(Sink(id="downstream"))
    for source, target in zip(chain, chain[1:], strict=False):
        system.add_edge(Edge(id=f"{source}_to_{target}", source=source, target=target))
    system.validate()
    return system


def build_river_farm(inflows: tuple[float, ...]) -> WaterSystem:
    """Build the three-block system river → farm → downstream: no reservoir, the farm takes what the river brings.

    Args:
        inflows: Monthly river inflow in Mm³.

    Returns:
        A validated system, not yet simulated.
    """
    years = len(inflows) // 12
    system = WaterSystem(frequency=Frequency.MONTHLY)
    system.add_node(Source(id="river", inflow=TimeSeries(values=list(inflows))))
    system.add_node(Demand(id="farm", requirement=TimeSeries(values=list(MONTHLY_NEED_MM3) * years)))
    system.add_node(Sink(id="downstream"))
    for source, target in (("river", "farm"), ("farm", "downstream")):
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


def simulate_without_reservoir(inflows: tuple[float, ...]) -> RunResult:
    """Run the three-block system (no reservoir) through TaqSim: what the farm gets straight from the river.

    The result has the shape of a plan's run so that it can be drawn next to one; its plan is "no rationing" and
    its storage is zero throughout, as there is nothing to store water in.
    """
    system = build_river_farm(inflows)
    system.simulate(len(inflows))
    shortage = shortage_by_month(system)
    return RunResult(
        plan=NO_RATIONING, scores=_scores(shortage), storage=np.zeros(len(inflows)), shortage_by_month=shortage
    )


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


@dataclass(frozen=True)
class WinterScores:
    """How a winter plan did: what the farm and the winter fields did not get, and the farm's worst month."""

    summer_shortage: float  # Mm³ per year the farm did not get
    winter_shortage: float  # Mm³ per year the winter fields did not get
    worst_month: float  # % of its need the farm did not get in its worst month


@dataclass(frozen=True)
class WinterRun:
    plan: Plan
    winter: WinterPlan
    scores: WinterScores
    storage: np.ndarray  # Mm³ at the end of each month
    winter_delivered_by_year: np.ndarray  # Mm³ the winter fields received in each winter


def _deficit_by_year(system: WaterSystem, node_id: str) -> np.ndarray:
    steps = len(system.nodes["river"].inflow.values)
    return _padded(_monthly(system.nodes[node_id], DeficitRecorded, "deficit"), steps).reshape(-1, 12)


def _winter_scores(system: WaterSystem) -> WinterScores:
    farm, fields = _deficit_by_year(system, "farm"), _deficit_by_year(system, "winter_fields")
    return WinterScores(
        summer_shortage=float(farm[:, list(SUMMER_MONTHS)].sum() / len(farm)),
        winter_shortage=float(fields[:, list(WINTER_MONTHS)].sum() / len(fields)),
        worst_month=float(shortage_by_month(system).max()),
    )


def simulate_winter(
    inflows: tuple[float, ...],
    winter: WinterPlan = WINTER_IN_FULL,
    plan: Plan = SUMMER_PLAN_FOR_WINTER,
    forecast: tuple[float, ...] | None = None,
) -> WinterRun:
    """Run the five-block system through TaqSim and read off storage, winter deliveries and scores."""
    system = build_system(inflows, plan, winter=winter, forecast=forecast)
    system.simulate(len(inflows))
    delivered = WINTER_FIELDS_TOTAL_MM3 - _deficit_by_year(system, "winter_fields").sum(axis=1)
    return WinterRun(
        plan=plan,
        winter=winter,
        scores=_winter_scores(system),
        storage=_storage_path(system),
        winter_delivered_by_year=delivered,
    )


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


# --- Many winter plans -------------------------------------------------------------------------------------


WINTER_GOALS = ("summer_shortage", "winter_shortage")


def winter_grid(
    n_trigger: int = 21, n_ration: int = 21, trigger_max: float = WINTER_TRIGGER_MAX_MM3
) -> list[WinterPlan]:
    """Evenly spaced winter plans covering every trigger (0 to `trigger_max`) and every ration (0 to 1)."""
    return [
        WinterPlan(trigger=float(trigger), ration=float(ration))
        for trigger in np.linspace(0.0, trigger_max, n_trigger)
        for ration in np.linspace(0.0, 1.0, n_ration)
    ]


def score_winter_plans(
    inflows: tuple[float, ...],
    winter_plans: list[WinterPlan],
    plan: Plan = SUMMER_PLAN_FOR_WINTER,
    forecast: tuple[float, ...] | None = None,
) -> pd.DataFrame:
    """Run every winter plan, with the summer plan fixed, and tabulate its scores.

    Returns:
        One row per winter plan with `winter_trigger`, `winter_ration`, `summer_shortage`, `winter_shortage`,
        `worst_month` and `unbeaten` (no other plan in the table has both a smaller summer and a smaller winter
        shortage).
    """
    rows = []
    for winter in winter_plans:
        scores = simulate_winter(inflows, winter, plan=plan, forecast=forecast).scores
        rows.append((winter.trigger, winter.ration, scores.summer_shortage, scores.winter_shortage, scores.worst_month))
    columns = ["winter_trigger", "winter_ration", *WINTER_GOALS, "worst_month"]
    table = pd.DataFrame(rows, columns=columns)
    table["unbeaten"] = unbeaten(table[list(WINTER_GOALS)].to_numpy().round(6))
    return table


def winter_front_of(table: pd.DataFrame) -> pd.DataFrame:
    """The distinct unbeaten (summer shortage, winter shortage) pairs of a winter score table, smallest summer
    shortage first."""
    ties_first = table[table["unbeaten"]].sort_values(["winter_ration", "winter_trigger"], ascending=[False, True])
    front = ties_first.round(dict.fromkeys(WINTER_GOALS, 6)).drop_duplicates(list(WINTER_GOALS))
    return front.sort_values("summer_shortage").reset_index(drop=True)


def least_winter_shortage(table: pd.DataFrame, summer_cap: float) -> float:
    """The smallest winter shortage among the plans whose summer shortage is at most `summer_cap` (NaN if none)."""
    within = table[table["summer_shortage"] <= summer_cap + 1e-9]
    return float(within["winter_shortage"].min()) if len(within) else float("nan")


def winter_plan_within(table: pd.DataFrame, summer_cap: float) -> WinterPlan:
    """The unbeaten winter plan with the least winter shortage whose summer shortage is at most `summer_cap`.

    Raises:
        ValueError: If no unbeaten plan keeps the summer shortage within the cap.
    """
    front = winter_front_of(table)
    within = front[front["summer_shortage"] <= summer_cap + 1e-9]
    if within.empty:
        raise ValueError(f"no unbeaten plan keeps the summer shortage within {summer_cap:g} Mm³ per year")
    row = within.iloc[-1]
    return WinterPlan(trigger=float(row["winter_trigger"]), ration=float(row["winter_ration"]))


def score_by_skill(
    inflows: tuple[float, ...],
    skills: tuple[float, ...],
    winter_plans: list[WinterPlan] | None = None,
    plan: Plan = SUMMER_PLAN_FOR_WINTER,
) -> dict[float, pd.DataFrame]:
    """The winter score table for a forecast of each skill, keyed by skill."""
    winter_plans = winter_plans or winter_grid()
    return {
        skill: score_winter_plans(inflows, winter_plans, plan, seasonal_forecast(inflows, skill)) for skill in skills
    }


def forecast_value(tables: dict[float, pd.DataFrame], summer_cap: float) -> pd.DataFrame:
    """For each forecast skill, the smallest winter shortage that keeps the summer shortage within `summer_cap`.

    Args:
        tables: Winter score tables keyed by forecast skill, as from `score_by_skill`.
        summer_cap: The summer shortage, Mm³ per year, that the plans may not exceed.

    Returns:
        One row per skill with `skill` and `winter_shortage` (Mm³ per year), in order of skill.
    """
    rows = [(skill, least_winter_shortage(table, summer_cap)) for skill, table in sorted(tables.items())]
    return pd.DataFrame(rows, columns=["skill", "winter_shortage"])


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

# One look for every figure of the coursebook, the notebooks and the slides: the typeface and palette of the course
# pages, no chart junk, text kept as text in SVG so that the web page renders it crisp at any size. The settings are
# applied when a figure is made (`_styled`), not globally, so that other notebooks in the same kernel are untouched.
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
    "xtick.major.size": 3.0,
    "ytick.major.size": 3.0,
    "legend.fontsize": 8.5,
    "legend.frameon": False,
    "legend.labelcolor": SECONDARY,
    "lines.linewidth": 1.6,
    "lines.solid_capstyle": "round",
    "figure.facecolor": "white",
    "figure.dpi": 150,  # the notebooks show PNG; the web page and the slides use SVG
    "savefig.dpi": 200,
    "svg.fonttype": "none",  # text stays text in SVG
    "axes.prop_cycle": mpl.cycler(color=[WATER, SHORTAGE, GREEN, "#8e6bd6", MUTED]),
}


def _styled(draw):
    """Apply the coursebook's figure style while `draw` makes its figure."""

    def wrapped(*args, **kwargs):
        with mpl.rc_context(_RC):
            return draw(*args, **kwargs)

    wrapped.__name__, wrapped.__doc__ = draw.__name__, draw.__doc__
    return wrapped


def _style(ax: plt.Axes) -> None:
    """What the rc settings cannot do per axis: a y axis that starts at the bottom spine, no clutter."""
    ax.grid(True, axis="y", color=GRID, linewidth=0.6)
    ax.grid(False, axis="x")
    ax.tick_params(length=3.0, width=0.6)
    ax.spines["bottom"].set_color(AXIS)
    ax.spines["left"].set_color(AXIS)


def _label_line(ax: plt.Axes, x: float, y: float, text: str, color: str, dy: float = 0.0, ha: str = "left") -> None:
    """A label written at the end of a line, in the line's colour, instead of a legend entry."""
    ax.annotate(
        text,
        (x, y),
        xytext=(4 if ha == "left" else -4, dy),
        textcoords="offset points",
        ha=ha,
        va="center",
        fontsize=8.5,
        color=color,
    )


def _score_line(scores: Scores) -> str:
    return (
        f"{scores.years_short} of {YEARS} years short · {scores.mean_shortage:.1f} Mm³/yr missed · "
        f"worst month {scores.worst_month:.0f} %"
    )


def _titles(ax: plt.Axes, label: str, scores: Scores | None) -> None:
    """A two-line header: the plan's name in bold, its scores in a muted line under it."""
    if scores is None:
        ax.set_title(label, loc="left")
        return
    ax.set_title(label, loc="left", pad=16)
    ax.text(0, 1.015, _score_line(scores), transform=ax.transAxes, fontsize=8.5, color=SECONDARY, va="bottom")


NETWORK_NODES: tuple[tuple[str, str, str], ...] = (
    ("river", "Source", "inflow from a time series"),
    ("reservoir", "Storage", "stores, loses and releases water"),
    ("farm", "Demand", "asks for water, records deficits"),
    ("downstream", "Sink", "takes what is left"),
)
NETWORK_EDGES: tuple[tuple[str, str], ...] = (("river", "reservoir"), ("reservoir", "farm"), ("farm", "downstream"))
_NODE_MARKERS = {"Source": "o", "Storage": "s", "Demand": "h", "Sink": "v"}


WINTER_NETWORK_NODES: tuple[tuple[str, str, str], ...] = (
    *NETWORK_NODES[:3],
    ("winter_fields", "Demand", "winter wheat and leaching"),
    NETWORK_NODES[3],
)
WINTER_NETWORK_EDGES: tuple[tuple[str, str], ...] = (
    ("river", "reservoir"),
    ("reservoir", "farm"),
    ("farm", "winter_fields"),
    ("winter_fields", "downstream"),
)


RIVER_FARM_NODES: tuple[tuple[str, str, str], ...] = (NETWORK_NODES[0], NETWORK_NODES[2], NETWORK_NODES[3])
RIVER_FARM_EDGES: tuple[tuple[str, str], ...] = (("river", "farm"), ("farm", "downstream"))


@_styled
def plot_network(winter: bool = False, reservoir: bool = True) -> Figure:
    """The model as TaqSim sees it: four nodes joined by three edges, water flowing left to right (five nodes and
    four edges with the winter fields; three nodes and two edges without the reservoir)."""
    if winter:
        nodes, edges = WINTER_NETWORK_NODES, WINTER_NETWORK_EDGES
    elif reservoir:
        nodes, edges = NETWORK_NODES, NETWORK_EDGES
    else:
        nodes, edges = RIVER_FARM_NODES, RIVER_FARM_EDGES
    spacing = 3.4 if winter else 2.4
    fig, ax = plt.subplots(figsize=(11.2 if winter else 8.0, 2.4))
    positions = {node_id: (i * spacing, 0.0) for i, (node_id, _, _) in enumerate(nodes)}
    for source, target in edges:
        (x0, y0), (x1, y1) = positions[source], positions[target]
        ax.annotate(
            "",
            xy=(x1 - 0.55, y1),
            xytext=(x0 + 0.55, y0),
            arrowprops={"arrowstyle": "-|>", "color": WATER, "linewidth": 1.8, "shrinkA": 0, "shrinkB": 0},
        )
        ax.text(
            (x0 + x1) / 2,
            0.2,
            f"{source}_to_{target}",
            ha="center",
            fontsize=6.5 if winter else 7.5,
            color=MUTED,
            family="monospace",
        )
    for node_id, kind, note in nodes:
        x, y = positions[node_id]
        ax.scatter(x, y, s=3000, marker=_NODE_MARKERS[kind], color=SURFACE, edgecolors=INK, linewidths=1.4, zorder=3)
        label_y = y + 0.08 if kind == "Sink" else y  # a triangle's visual centre sits above its middle
        size = 7 if kind == "Sink" or len(node_id) > 10 else 8  # "downstream" and "winter_fields" must fit their shapes
        ax.text(x, label_y, node_id, ha="center", va="center", fontsize=size, color=INK, weight="bold", zorder=4)
        ax.text(x, -0.62, kind, ha="center", va="top", fontsize=8.5, color=SECONDARY)
        ax.text(x, -0.85, note, ha="center", va="top", fontsize=7.5, color=MUTED)
    pad = (spacing * (len(NETWORK_NODES) - 1) - positions["downstream"][0]) / 2  # the three blocks stay centred
    ax.set_xlim(-0.9 - pad, positions["downstream"][0] + 0.9 + pad)
    ax.set_ylim(-1.2, 0.55)
    ax.axis("off")
    fig.tight_layout()
    return fig


@_styled
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


@_styled
def plot_inflows(inflows: tuple[float, ...]) -> Figure:
    """Winter and summer inflow of every year, against the reservoir size and the summer need."""
    winter, summer = season_totals(inflows)
    years = np.arange(1, len(winter) + 1)
    fig, ax = plt.subplots(figsize=(8.0, 3.2))
    ax.plot(years, summer, color=SHORTAGE, linewidth=1.5)
    ax.plot(years, winter, color=WATER, linewidth=1.5)
    ax.axhline(SUMMER_NEED_MM3, color=INK, linewidth=0.9, linestyle=(0, (4, 3)))
    top = max(summer.max(), winter.max()) * 1.12
    ax.text(
        1,
        top * 0.97,
        "Summer inflow, April to September: when the farm irrigates",
        color=SHORTAGE,
        fontsize=8.5,
        va="top",
    )
    ax.text(
        1, top * 0.88, "Winter inflow, October to March: when the reservoir fills", color=WATER, fontsize=8.5, va="top"
    )
    ax.text(
        1,
        top * 0.79,
        f"Dashed: what the farm needs in summer, {SUMMER_NEED_MM3:g} Mm³",
        color=INK,
        fontsize=8.5,
        va="top",
    )
    ax.set_xlim(0, len(years) + 1)
    ax.set_ylim(0, top)
    ax.set_xlabel("Year")
    ax.set_ylabel("Inflow (Mm³ per season)")
    _style(ax)
    fig.tight_layout()
    return fig


@_styled
def plot_runs(runs: dict[str, RunResult], first_year: int = 1, window_years: int = 20) -> Figure:
    """One row per plan: each year's worst month over all years (left, the shown window shaded) and storage over
    a window of years (right)."""
    fig, axes = plt.subplots(
        len(runs),
        2,
        figsize=(8.0, 2.45 * len(runs) + 0.5),
        sharex="col",
        sharey="col",
        squeeze=False,
        gridspec_kw={"width_ratios": [1.25, 1.0]},
    )
    for (label, run), (left, right) in zip(runs.items(), axes, strict=True):
        worst = run.worst_month_by_year
        left.axvspan(first_year - 0.5, first_year + window_years - 0.5, color=WATER, alpha=0.1, linewidth=0)
        left.bar(np.arange(1, len(worst) + 1), worst, width=0.75, color=SHORTAGE, linewidth=0)
        left.set_xlim(0, len(worst) + 1)
        left.set_ylim(0, 100)
        left.set_yticks([0, 25, 50, 75, 100])
        left.set_ylabel("Worst month of the year\n(% of its need not delivered)")
        _titles(left, label, run.scores)
        months = np.arange(12 * (first_year - 1), 12 * (first_year - 1 + window_years))
        right.axhline(CAPACITY_MM3, color=AXIS, linewidth=0.8, linestyle=(0, (3, 3)))
        right.text(
            first_year + window_years - 0.2, CAPACITY_MM3, "full", color=MUTED, fontsize=8, ha="right", va="bottom"
        )
        right.plot(months / 12 + 1, run.storage[months], color=WATER, linewidth=1.3)
        if run.plan.trigger > 0.0 and run.plan.ration < 1.0:
            right.axhline(run.plan.trigger, color=SHORTAGE, linewidth=0.9, linestyle=(0, (3, 3)))
            right.text(first_year + 0.1, run.plan.trigger, "trigger", color=SHORTAGE, fontsize=8, va="bottom")
        right.xaxis.set_major_locator(MaxNLocator(integer=True))
        right.set_xlim(first_year, first_year + window_years)
        right.set_ylim(0, CAPACITY_MM3 * 1.12)
        right.set_ylabel("Water in the reservoir (Mm³)")
        _style(left)
        _style(right)
    axes[-1][0].set_xlabel("Year (all 100 years; shaded: the window shown on the right)")
    axes[-1][1].set_xlabel(f"Year ({window_years} years around the worst drought)")
    fig.tight_layout(h_pad=1.4)
    return fig


@_styled
def plot_shortage_years(runs: dict[str, RunResult]) -> Figure:
    """One row per run: the worst month of each of the 100 years, so that two systems can be compared year by year."""
    fig, axes = plt.subplots(len(runs), 1, figsize=(8.0, 2.05 * len(runs) + 0.5), sharex=True, squeeze=False)
    for (label, run), (ax,) in zip(runs.items(), axes, strict=True):
        worst = run.worst_month_by_year
        ax.bar(np.arange(1, len(worst) + 1), worst, width=0.75, color=SHORTAGE, linewidth=0)
        ax.set_xlim(0, len(worst) + 1)
        ax.set_ylim(0, 100)
        ax.set_yticks([0, 50, 100])
        ax.set_ylabel("Worst month\n(% short)")
        _titles(ax, label, run.scores)
        _style(ax)
    axes[-1][0].set_xlabel("Year")
    fig.tight_layout(h_pad=1.4)
    return fig


@_styled
def plot_score_maps(table: pd.DataFrame) -> Figure:
    """Each score for every plan: trigger across, ration up, darker = worse."""
    columns = [
        ("mean_shortage", "Average shortage (Mm³/yr)"),
        ("worst_month", "Worst month (% short)"),
        ("years_short", "Years short (of 100)"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(9.0, 3.2), sharey=True)
    triggers, rations = np.sort(table["trigger"].unique()), np.sort(table["ration"].unique())
    for ax, (column, title) in zip(axes, columns, strict=True):
        values = table.pivot(index="ration", columns="trigger", values=column).to_numpy()
        mesh = ax.pcolormesh(triggers, rations * 100, values, cmap=BLUE_RAMP, shading="nearest", rasterized=True)
        colorbar = fig.colorbar(mesh, ax=ax, fraction=0.05, pad=0.03)
        colorbar.ax.tick_params(labelsize=7.5, colors=MUTED, length=2)
        colorbar.outline.set_visible(False)
        ax.set_title(title, fontsize=9.5)
        ax.set_xlabel("Trigger (Mm³ in store)")
        _style(ax)
        ax.grid(False)
    axes[0].set_ylabel("Ration (% of need delivered)")
    fig.tight_layout()
    return fig


@_styled
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
    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    beaten = table[~table["unbeaten"]]
    front = front_of(table)
    ax.scatter(beaten["mean_shortage"], beaten["worst_month"], s=13, color=REFERENCE, linewidths=0, label="beaten plan")
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
            f"{beyond} plans lie further right",
            transform=ax.transAxes,
            ha="right",
            fontsize=8,
            color=MUTED,
        )
    ax.set_xlabel("Average shortage (Mm³ per year)")
    ax.set_ylabel("Worst month (% of its need not delivered)")
    ax.set_xlim(0, MEAN_SHORTAGE_AXIS_MAX)
    ax.set_ylim(0, 100)
    _better_arrows(ax)
    ax.legend(loc="upper right")
    _style(ax)
    fig.tight_layout()
    return fig


def _better_arrows(ax: plt.Axes) -> None:
    """Two small reminders in the corner: left is better, down is better."""
    ax.text(
        0.01,
        0.02,
        "better: further left (less water missed) and further down (milder worst month)",
        transform=ax.transAxes,
        fontsize=8,
        color=MUTED,
        ha="left",
        va="bottom",
    )


@_styled
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
    ax.set_xlabel("Average shortage (Mm³ per year)")
    ax.set_ylabel("Worst month (% of its need not delivered)")
    ax.set_xlim(0, MEAN_SHORTAGE_AXIS_MAX)
    ax.set_ylim(0, 100)
    _better_arrows(ax)
    ax.legend(loc="upper right")
    _style(ax)
    fig.tight_layout()
    return fig


@_styled
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
    right.set_xlabel("Average shortage (Mm³ per year)")
    right.set_ylabel("Worst month (% of its need not delivered)")
    right.set_title("The unbeaten plans", loc="left", fontsize=10, color=INK)
    _better_arrows(right)
    for ax in (left, right):
        ax.legend()
        _style(ax)
    fig.tight_layout()
    return fig


# --- The winter fields and the forecast --------------------------------------------------------------------


_FRONT_COLORS = (WATER, SHORTAGE, "#1baf7a", "#8e6bd6", MUTED)


@_styled
def plot_winter_fronts(fronts: dict[str, pd.DataFrame]) -> Figure:
    """Compare the unbeaten winter plans of two or more winter score tables (e.g. without and with a forecast)."""
    fig, ax = plt.subplots(figsize=(7.0, 3.8))
    for (label, table), color in zip(fronts.items(), _FRONT_COLORS, strict=False):
        front = winter_front_of(table)
        ax.plot(
            front["summer_shortage"],
            front["winter_shortage"],
            color=color,
            linewidth=1.6,
            drawstyle="steps-post",
            marker="o",
            markersize=5,
            markeredgecolor=SURFACE,
            label=label,
        )
    ax.set_xlabel("Summer shortage: water the farm did not get (Mm³ per year)")
    ax.set_ylabel("Winter shortage: water the winter fields\ndid not get (Mm³ per year)")
    ax.set_xlim(left=0)
    ax.set_ylim(0, WINTER_FIELDS_TOTAL_MM3 * 1.05)
    ax.text(
        0.01,
        0.02,
        "better: further left and further down",
        transform=ax.transAxes,
        fontsize=8,
        color=MUTED,
        ha="left",
        va="bottom",
    )
    ax.legend(loc="upper right")
    _style(ax)
    fig.tight_layout()
    return fig


@_styled
def plot_winter_decisions(
    runs: dict[str, WinterRun], inflows: tuple[float, ...], first_year: int = 1, window_years: int = 20
) -> Figure:
    """Top: what the winter fields received each winter under each plan. Bottom: the summer inflow that followed."""
    _, summer = season_totals(inflows)
    years = np.arange(first_year, first_year + window_years)
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(8.0, 4.6), sharex=True)
    width = 0.8 / len(runs)
    for i, ((label, run), color) in enumerate(zip(runs.items(), _FRONT_COLORS, strict=False)):
        offsets = years + (i - (len(runs) - 1) / 2) * width
        top.bar(offsets, run.winter_delivered_by_year[years - 1], width=width, color=color, label=label)
    top.axhline(WINTER_FIELDS_TOTAL_MM3, color=MUTED, linewidth=1.0)
    top.text(years[0] - 0.4, WINTER_FIELDS_TOTAL_MM3 + 0.3, "what the winter fields ask for", color=MUTED, fontsize=7.5)
    top.set_ylim(0, WINTER_FIELDS_TOTAL_MM3 * 1.25)
    top.set_ylabel("Delivered in winter (Mm³)")
    top.legend(loc="upper right", ncol=len(runs))
    bottom.bar(years, summer[years - 1], width=0.7, color=WATER, alpha=0.75)
    bottom.axhline(SUMMER_NEED_MM3, color=MUTED, linewidth=1.0)
    bottom.text(years[0] - 0.4, SUMMER_NEED_MM3 + 1.0, "what the farm needs in summer", color=MUTED, fontsize=7.5)
    bottom.set_ylabel("The summer that followed:\ninflow (Mm³)")
    bottom.set_xlabel(f"Year (a window of {window_years} years)")
    bottom.xaxis.set_major_locator(MaxNLocator(integer=True))
    for ax in (top, bottom):
        _style(ax)
    fig.tight_layout()
    return fig


@_styled
def plot_forecast_skill(inflows: tuple[float, ...], skills: tuple[float, ...] = (0.5, 0.9)) -> Figure:
    """One panel per skill: the forecast of each summer against the summer that came."""
    _, summer = season_totals(inflows)
    fig, axes = plt.subplots(1, len(skills), figsize=(3.4 * len(skills), 3.3), sharex=True, sharey=True)
    top = float(max(summer.max(), max(max(seasonal_forecast(inflows, s)) for s in skills))) * 1.05
    for ax, skill in zip(np.atleast_1d(axes), skills, strict=True):
        forecast = np.asarray(seasonal_forecast(inflows, skill))
        ax.plot([0, top], [0, top], color=MUTED, linewidth=1.0)
        ax.scatter(summer, forecast, s=14, color=WATER, alpha=0.8, edgecolors="none")
        ax.set_title(f"skill {skill:g}", fontsize=9.5)
        ax.set_xlabel("The summer that came (Mm³)")
        ax.set_xlim(0, top)
        ax.set_ylim(0, top)
        _style(ax)
    np.atleast_1d(axes)[0].set_ylabel("The forecast (Mm³)")
    fig.tight_layout()
    return fig


@_styled
def plot_forecast_value(curve: pd.DataFrame, no_forecast: float, summer_cap: float) -> Figure:
    """The winter shortage the forecast leaves, against its skill, with the no-forecast level for comparison."""
    fig, ax = plt.subplots(figsize=(6.8, 3.6))
    ax.axhline(no_forecast, color=SHORTAGE, linewidth=1.4, label="no forecast: storage alone")
    ax.plot(
        curve["skill"],
        curve["winter_shortage"],
        color=WATER,
        linewidth=1.6,
        marker="o",
        markersize=5,
        markeredgecolor=SURFACE,
        label="with the forecast",
    )
    ax.set_xlabel("Forecast skill (correlation with the summer that came)")
    ax.set_ylabel(f"Winter shortage (Mm³ per year)\nwith the summer shortage held to {summer_cap:g} Mm³")
    ax.set_xlim(0, 1)
    ax.set_ylim(bottom=0)
    ax.legend()
    _style(ax)
    fig.tight_layout()
    return fig
