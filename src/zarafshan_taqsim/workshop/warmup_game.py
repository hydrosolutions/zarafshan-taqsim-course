"""Warm-up game: a Zarafshan-like river in sixteen TaqSim blocks (reference model on TaqSim v0.1.4).

The smallest network that still has the Zarafshan's characteristic users, with the numbers and operating calendar
of the full workshop game (`zarafshan_game.py`) lumped: one hydrological year (Oct-Sep) in twelve monthly steps,
run for the dry year (Oct 2020 - Sep 2021), the 2017-2022 mean year and the wet year (Oct 2018 - Sep 2019).
Volumes are Mm³ per month.

    inflow (Source) -> upper_river (Reach) -> headworks (Splitter) -+-> transfers (Sink)
                                                                    +-> main_canal (Reach, seepage) -> irrigation
                                                                    +-> river -> cities (Demand)
    irrigation (Demand, upper fields) -> drain_store (Storage, slow return) --+
    cities -------------------------------------------------------------------+-> weir (Splitter)
    weir -+-> reservoir (Storage) -+
          +-> river ---------------+-> lower_headworks (Splitter) -+-> power_plant (Demand) ------------------+
                                                                   +-> lower_irrigation (Demand)              |
                                                                   |     -> lower_drain (Storage) ------------+
                                                                   +-> river ---------------------------------+
    ... -> downstream (Demand: e-flow + downstream users) -> sink (Sink)

Irrigation is two blocks, as on the river: the Samarkand canals above the reservoir, and the Kattakurgan command
and Navoi below it. The reservoir lies beside the river between them, as Kattakurgan does: from November to March
the weir stores a share of the river above the power plant's intake, and from March to November the reservoir
releases a share of what is missing at the lower headworks for the power plant, the lower canal and the river
reserve. The River reserve applies at both headworks. Drain water does not return in the same month: each
irrigation block drains into a store that gives back a fixed share of its content each month, as in the full
game; each plan starts the year with the store contents that repeat under that plan. The power plant takes its
cooling water at the lower headworks and returns what it does not evaporate. Every block type of TaqSim appears
except PassThrough; the page built from this model explains each one. The cities are served first: the headworks
leave the cities' need in the river, plus the reserve. The levers move in fixed steps, so every plan a player can
set is one of `len(LEVER_GRID)` combinations; all of them are run by `exact_front`, which makes "no other plan
beats this one" a checked statement instead of a search result.
The browser game re-implements these equations in JavaScript (workshop/warmup_game/game/model.js) and is checked
against the `reference_cases` written by `export_game_data`.
"""

import importlib.metadata
import itertools
import json
import logging
import random
import time
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import ClassVar

import numpy as np
from taqsim import (
    Demand,
    Edge,
    NoReachLoss,
    NoRouting,
    Objective,
    Reach,
    Sink,
    Source,
    Splitter,
    Storage,
    Strategy,
    TimeSeries,
    WaterSystem,
)
from taqsim import minimize as minimize_objectives
from taqsim import optimize as taqsim_optimize
from taqsim.common import SEEPAGE, ParamSpec
from taqsim.node import NoLoss
from taqsim.node.events import (
    DeficitRecorded,
    WaterDistributed,
    WaterLost,
    WaterOutput,
    WaterReceived,
    WaterReleased,
    WaterSpilled,
    WaterStored,
)
from taqsim.time import Frequency, Timestep

from zarafshan_taqsim.workshop.zarafshan_game import (
    DAYS,
    DRAIN_CAPACITY_MM3,
    DRAINAGE_RECESSION,
    DRAINAGE_SHARE,
    EVAPORATION_MM,
    FILL_CAP_M3S,
    FILL_MONTHS,
    INDUSTRY_CONSUMPTIVE,
    INFLOW_M3S,
    IRRIGATION_CAP_M3S,
    IRRIGATION_REQ_MM3,
    JIZZAKH_M3S,
    KASHKADARYA_M3S,
    MONTHS,
    MUNICIPAL_RETURN,
    N_STEPS,
    NAVOI_GAUGE_M3S,
    POPULATION,
    RELEASE_CAP_M3S,
    RELEASE_MONTHS,
    RESERVOIR_CAPACITY_MM3,
    RESERVOIR_DEAD_MM3,
    START_STORAGE_MM3,
    TPP_CAPACITY_FACTOR,
    TPP_MIN_INTAKE_M3S,
    TPP_RIVER_COOLED_MW,
    TPP_WITHDRAWAL_M3S,
    VA_AREA_KM2,
    VA_VOLUME_MM3,
    YEAR_LABELS,
    YEARS,
    LinearRecession,
    TableEvaporation,
    flow,
    volume,
)

logger = logging.getLogger(__name__)

ETA_CANAL = 0.65  # conveyance efficiency (full model)
ETA_FIELD = 0.75  # field efficiency (full model)
ETA = ETA_CANAL * ETA_FIELD  # share of the water taken at the headworks that the crop uses
MUNICIPAL_LCD = 150.0  # litres per person per day, gross
UPSTREAM_INDUSTRY_M3S = 3.0
TPP_CONSUMPTIVE_M3S = 8.0
EFLOW_SHARE = 0.20  # of the natural monthly inflow
DOWNSTREAM_POPULATION = 2_099_069  # Bukhara region
DOWNSTREAM_IRRIGATION_MM3 = 150.0  # per year, spread like the upstream crop requirement
# The two irrigation blocks: the Samarkand canals above the reservoir, the Kattakurgan command and Navoi below it.
UPPER_GROUPS = ("samarkand_irrigation",)
LOWER_GROUPS = ("kattakurgan_irrigation", "navoi_irrigation")
CANAL_CAP_M3S = sum(IRRIGATION_CAP_M3S[g] for g in UPPER_GROUPS)
LOWER_CANAL_CAP_M3S = sum(IRRIGATION_CAP_M3S[g] for g in LOWER_GROUPS)

# Crop requirement (Mm³/month): the three irrigation groups of the full game in two blocks, and their sum.
CROP_UPPER_MM3: tuple[float, ...] = tuple(sum(IRRIGATION_REQ_MM3[g][m] for g in UPPER_GROUPS) for m in range(N_STEPS))
CROP_LOWER_MM3: tuple[float, ...] = tuple(sum(IRRIGATION_REQ_MM3[g][m] for g in LOWER_GROUPS) for m in range(N_STEPS))
CROP_MM3: tuple[float, ...] = tuple(u + lo for u, lo in zip(CROP_UPPER_MM3, CROP_LOWER_MM3, strict=True))
# What a canal must take at its headworks so that the crop gets its requirement.
GROSS_MM3: tuple[float, ...] = tuple(c / ETA for c in CROP_UPPER_MM3)
GROSS_LOWER_MM3: tuple[float, ...] = tuple(c / ETA for c in CROP_LOWER_MM3)
# Of each unit taken at the headworks the crop uses ETA. Of the losses (1 - ETA), the share DRAINAGE_SHARE drains
# back to the river and the rest is lost for good. The game books the part lost for good on the main canal and the
# crop use and the drain water on the irrigation block, so the three shares add up to one.
CANAL_LOSS = (1.0 - DRAINAGE_SHARE) * (1.0 - ETA)
DRAIN_SHARE_OF_GROSS = DRAINAGE_SHARE * (1.0 - ETA)
# The evaporation series is pan evaporation (project lead, 2026-10-05). Open water loses less: 0.6 of the pan
# depth is 1,402 mm a year, inside the 1,135-1,458 mm of Gapparov et al. 2019 (workshop/zarafshan_game/DESIGN.md:166).
PAN_COEFFICIENT = 0.6
RESERVOIR_EVAPORATION_MM: tuple[float, ...] = tuple(PAN_COEFFICIENT * depth for depth in EVAPORATION_MM)
# What must arrive at the end of the canal, and the share of it the crop uses (the rest drains back).
FIELD_NEED_MM3: tuple[float, ...] = tuple(g * (1.0 - CANAL_LOSS) for g in GROSS_MM3)
IRRIGATION_CF = ETA / (1.0 - CANAL_LOSS)

# Canal transfers to Jizzakh and Kashkadarya (2017-2022 monthly means): fixed here, a lever in the full game.
TRANSFERS_MM3: tuple[float, ...] = tuple(
    volume(j + k, d) for j, k, d in zip(JIZZAKH_M3S, KASHKADARYA_M3S, DAYS, strict=True)
)
_UPSTREAM_PEOPLE_MM3_PER_DAY = sum(POPULATION.values()) * MUNICIPAL_LCD * 1e-9
_UPSTREAM_INDUSTRY_MM3_PER_DAY = UPSTREAM_INDUSTRY_M3S * 86_400 / 1e6
CITY_MM3: tuple[float, ...] = tuple((_UPSTREAM_PEOPLE_MM3_PER_DAY + _UPSTREAM_INDUSTRY_MM3_PER_DAY) * d for d in DAYS)
CITY_CF = (
    (1.0 - MUNICIPAL_RETURN) * _UPSTREAM_PEOPLE_MM3_PER_DAY + INDUSTRY_CONSUMPTIVE * _UPSTREAM_INDUSTRY_MM3_PER_DAY
) / (_UPSTREAM_PEOPLE_MM3_PER_DAY + _UPSTREAM_INDUSTRY_MM3_PER_DAY)
TPP_MM3: tuple[float, ...] = tuple(volume(TPP_WITHDRAWAL_M3S, d) for d in DAYS)
TPP_MIN_MM3: tuple[float, ...] = tuple(volume(TPP_MIN_INTAKE_M3S, d) for d in DAYS)
TPP_CF = TPP_CONSUMPTIVE_M3S / TPP_WITHDRAWAL_M3S
DOWNSTREAM_PEOPLE_MM3 = DOWNSTREAM_POPULATION * MUNICIPAL_LCD * 365 * 1e-9
DOWNSTREAM_USERS_MM3: tuple[float, ...] = tuple(
    DOWNSTREAM_POPULATION * MUNICIPAL_LCD * 1e-9 * d + DOWNSTREAM_IRRIGATION_MM3 * c / sum(CROP_MM3)
    for d, c in zip(DAYS, CROP_MM3, strict=True)
)

EDGES: tuple[tuple[str, str], ...] = (
    ("inflow", "upper_river"),
    ("upper_river", "headworks"),
    ("headworks", "transfers"),
    ("headworks", "main_canal"),
    ("headworks", "cities"),
    ("main_canal", "irrigation"),
    ("irrigation", "drain_store"),
    ("drain_store", "weir"),
    ("cities", "weir"),
    ("weir", "reservoir"),
    ("weir", "lower_headworks"),
    ("reservoir", "lower_headworks"),
    ("lower_headworks", "power_plant"),
    ("lower_headworks", "lower_irrigation"),
    ("lower_headworks", "downstream"),
    ("power_plant", "downstream"),
    ("lower_irrigation", "lower_drain"),
    ("lower_drain", "downstream"),
    ("downstream", "sink"),
)
DEMANDS = ("irrigation", "cities", "power_plant", "lower_irrigation", "downstream")


@dataclass(frozen=True)
class Levers:
    """Player decisions, named as the same levers of the full game (L6, L3, L4 there)."""

    reserve_share: float = 0.15  # share of the natural inflow that each headworks leaves in the river
    fill_share: float = 0.4  # share of the river above the power plant's intake that the weir stores
    release_share: float = 1.0  # share of what is missing at the lower headworks that the reservoir covers


LEVER_BOUNDS: dict[str, tuple[float, float]] = {
    "reserve_share": (0.0, 0.4),
    "fill_share": (0.0, 0.8),
    "release_share": (0.0, 1.0),
}
# The sliders move in these steps, so the lever space is a finite grid that can be run completely.
LEVER_STEPS: dict[str, float] = {"reserve_share": 0.01, "fill_share": 0.05, "release_share": 0.05}
# Where TaqSim sees each lever (the reserve share is repeated on two rules; see WarmupSystem).
LEVER_PATHS: dict[str, str] = {
    "reserve_share": "headworks.split_policy.reserve_share",
    "fill_share": "weir.split_policy.fill_share",
    "release_share": "reservoir.release_policy.release_share",
}
# The four indicators the page compares plans on, all "higher is better".
AXES = ("irrigation_supply", "lower_irrigation_supply", "downstream_months", "end_storage")


def lever_values(name: str) -> tuple[float, ...]:
    """Every value the slider of this lever can take."""
    lo, hi = LEVER_BOUNDS[name]
    step = LEVER_STEPS[name]
    return tuple(round(lo + i * step, 6) for i in range(round((hi - lo) / step) + 1))


LEVER_GRID: tuple[tuple[float, ...], ...] = tuple(itertools.product(*(lever_values(name) for name in LEVER_PATHS)))


def snap(levers: Levers) -> Levers:
    """The nearest plan the sliders can set."""
    values = {}
    for name in LEVER_PATHS:
        lo, hi = LEVER_BOUNDS[name]
        step = LEVER_STEPS[name]
        values[name] = round(min(max(lo + round((getattr(levers, name) - lo) / step) * step, lo), hi), 6)
    return Levers(**values)


# --- Future worlds: the mean year under climate change ---------------------------------------------------------
# Monthly change factors of the Zarafshan inflow, October first: SSP3-7.0, median of the four climate models
# (GFDL-ESM4, IPSL-CM6A-LR, MRI-ESM2-0, UKESM1-0-LL), each period against the same model's 2012-2040. **Measured**
# 2026-10-06 (pandas) from the daily discharge series behind the climate impact report (Siegfried, Kreiner, Zhumabaev,
# Marti 2024, "21st-Century Climate Impacts in Upstream Zarafshan River Basin", hydrosolutions technical report,
# rev. 12 Nov 2024; files q_fut_sim_bcsd_<GCM>_ssp370_Zarafshan_2012_2099.csv). The report's own finding (read, ch. 4.2):
# the peak moves up to four weeks earlier and the third quarter's share of the year falls from one half to one third.
CLIMATE_FACTORS: dict[str, tuple[float, ...]] = {
    "mid_century": (0.898, 0.908, 0.941, 0.996, 1.07, 1.162, 1.424, 1.209, 1.034, 0.97, 0.969, 0.966),
    "late_century": (0.848, 0.913, 0.976, 1.055, 1.261, 1.593, 1.965, 1.343, 0.988, 0.812, 0.793, 0.886),
}
CLIMATE_SOURCE = (
    "Siegfried, Kreiner, Zhumabaev, Marti (2024): 21st-Century Climate Impacts in Upstream Zarafshan River Basin. "
    "hydrosolutions technical report, rev. 12 Nov 2024. SSP3-7.0, median of four climate models, relative to 2012-2040."
)
FUTURE_WORLDS: tuple[str, ...] = tuple(CLIMATE_FACTORS)
WORLDS: tuple[str, ...] = YEARS + FUTURE_WORLDS  # the three observed years and the two future worlds
WORLD_INFLOW_M3S: dict[str, tuple[float, ...]] = {
    **INFLOW_M3S,
    **{w: tuple(q * f for q, f in zip(INFLOW_M3S["median"], CLIMATE_FACTORS[w], strict=True)) for w in FUTURE_WORLDS},
}
WORLD_LABELS: dict[str, str] = {
    **YEAR_LABELS,
    "mid_century": "2041-2070: the mean year under climate change (SSP3-7.0)",
    "late_century": "2071-2099: the mean year under climate change (SSP3-7.0)",
}
WORLD_GAUGE_M3S: dict[str, tuple[float | None, ...]] = {**NAVOI_GAUGE_M3S, **{w: (None,) * 12 for w in FUTURE_WORLDS}}


def natural(year: str) -> tuple[float, ...]:
    """Natural inflow at Ravatkhoja (Mm³/month) for one of the observed years or future worlds."""
    if year not in WORLD_INFLOW_M3S:
        raise ValueError(f"unknown year {year!r}; choose one of {WORLDS}")
    return tuple(volume(q, d) for q, d in zip(WORLD_INFLOW_M3S[year], DAYS, strict=True))


def eflow(year: str) -> tuple[float, ...]:
    return tuple(EFLOW_SHARE * q for q in natural(year))


def downstream_requirement(year: str) -> tuple[float, ...]:
    """Flow owed to the river below the model: the e-flow plus the downstream users' withdrawals."""
    return tuple(e + u for e, u in zip(eflow(year), DOWNSTREAM_USERS_MM3, strict=True))


def kept_in_river(reserve_share: float, natural_inflow: float, city_need: float) -> float:
    """What the headworks leave in the river: the reserve, and on top of it what the cities need."""
    return reserve_share * natural_inflow + city_need


def needed_below_weir(year: str, reserve_share: float) -> tuple[float, ...]:
    """What the lower headworks want to pass on in each month: the power plant's intake, what the lower canal needs
    and the river reserve."""
    return tuple(
        plant + canal + reserve_share * q
        for plant, canal, q in zip(TPP_MM3, LOWER_CANAL_NEED_MM3, natural(year), strict=True)
    )


def canal_take(
    reserve_share: float, natural_inflow: float, transfer: float, city_need: float, canal_need: float
) -> float:
    """What the main canal takes at the headworks in a month."""
    river = max(natural_inflow - transfer, 0.0)
    return min(canal_need, max(river - kept_in_river(reserve_share, natural_inflow, city_need), 0.0))


def periodic_store(inputs: tuple[float, ...], recession: float) -> float:
    """Start content of a store that gives back `recession` of its content each month and ends the year where it
    started, for these monthly inputs."""
    keep = 1.0 - recession
    carried = 0.0
    decay = 1.0
    for value in inputs:
        carried = (carried + value) * keep
        decay = decay * keep
    return carried / (1.0 - decay)


def drain_inputs(
    reserve_share: float,
    natural_inflow: tuple[float, ...],
    transfers: tuple[float, ...],
    city_need: tuple[float, ...],
    canal_need: tuple[float, ...],
) -> tuple[float, ...]:
    """Water that drains from the fields into the ground in each month of the year."""
    return tuple(
        DRAIN_SHARE_OF_GROSS * canal_take(reserve_share, q, tr, city, need)
        for q, tr, city, need in zip(natural_inflow, transfers, city_need, canal_need, strict=True)
    )


def drain_return(
    reserve_share: float,
    natural_inflow: tuple[float, ...],
    transfers: tuple[float, ...],
    city_need: tuple[float, ...],
    canal_need: tuple[float, ...],
    month: int,
) -> float:
    """Drain water that returns to the river in `month`: the store receives the fields' drain water of each month
    and then gives back a fixed share of what it holds. It starts the year with what repeats under this plan."""
    inputs = drain_inputs(reserve_share, natural_inflow, transfers, city_need, canal_need)
    stored = periodic_store(inputs, DRAINAGE_RECESSION)
    returned = 0.0
    for m in range(month + 1):
        stored += inputs[m]
        returned = DRAINAGE_RECESSION * stored
        stored -= returned
    return returned


def arriving_at_weir(
    reserve_share: float,
    natural_inflow: tuple[float, ...],
    transfers: tuple[float, ...],
    city_need: tuple[float, ...],
    canal_need: tuple[float, ...],
    month: int,
) -> float:
    """What reaches the weir in a month: the river left by the canal and the cities, plus the returning drain water.

    The release rule of the reservoir needs this number and a TaqSim Storage does not see the river beside it, so
    the rule works it out from the inflow in the same way the blocks above the weir do.
    """
    m = month
    river = max(natural_inflow[m] - transfers[m], 0.0)
    at_cities = river - canal_take(reserve_share, natural_inflow[m], transfers[m], city_need[m], canal_need[m])
    back = drain_return(reserve_share, natural_inflow, transfers, city_need, canal_need, m)
    return at_cities - min(at_cities, city_need[m]) * CITY_CF + back


def _cap(q_m3s: float) -> tuple[float, ...]:
    return tuple(volume(q_m3s, d) for d in DAYS)


CANAL_NEED_MM3: tuple[float, ...] = tuple(min(g, c) for g, c in zip(GROSS_MM3, _cap(CANAL_CAP_M3S), strict=True))
LOWER_CANAL_NEED_MM3: tuple[float, ...] = tuple(
    min(g, c) for g, c in zip(GROSS_LOWER_MM3, _cap(LOWER_CANAL_CAP_M3S), strict=True)
)


def drain_store_start(year: str, reserve_share: float) -> float:
    """Content of the drain store on 1 October (Mm³): what repeats from year to year under this plan.

    Each plan is run as if it were used every year, so the store ends the year where it started and no plan lives
    off drain water it did not put in. (The full game starts its stores with what repeats under its starting plan,
    the same for every plan.)
    """
    inputs = drain_inputs(reserve_share, natural(year), TRANSFERS_MM3, CITY_MM3, CANAL_NEED_MM3)
    return periodic_store(inputs, DRAINAGE_RECESSION)


# --- Strategies ------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class HeadworksPolicy(Strategy):
    """Headworks: the transfer canals first; then the main canal takes its gross need, as far as the river above
    what must stay in it (the cities' need and the reserve) allows."""

    __params__: ClassVar[tuple[str, ...]] = ("reserve_share",)
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {"reserve_share": LEVER_BOUNDS["reserve_share"]}

    natural: tuple[float, ...] = field(default=(0.0,))
    city_need: tuple[float, ...] = field(default=(0.0,) * 12)
    transfers: tuple[float, ...] = field(default=(0.0,) * 12)
    canal_need: tuple[float, ...] = field(default=(0.0,))
    reserve_share: float = 0.15

    def split(self, node: Splitter, amount: float, t: Timestep) -> dict[str, float]:
        m = t.index % 12
        transfer = min(self.transfers[m], amount)
        river = amount - transfer
        keep = kept_in_river(self.reserve_share, self.natural[m], self.city_need[m])
        take = min(self.canal_need[m], max(river - keep, 0.0))
        return {"transfers": transfer, "main_canal": take, "cities": river - take}


@dataclass(frozen=True)
class WeirPolicy(Strategy):
    """Weir below the cities: the power plant's intake passes; of the rest, a share goes to the reservoir.

    Filling takes water from the river downstream: what is stored does not flow on in that month. The weir fills
    from November to March (the real reservoir rises from December to February), and never in a month in which the
    river is already too low for what the lower headworks want to pass on (then the reservoir releases instead).
    """

    __params__: ClassVar[tuple[str, ...]] = ("fill_share",)
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {"fill_share": LEVER_BOUNDS["fill_share"]}

    need_below: tuple[float, ...] = field(default=(0.0,) * 12)
    plant_need: tuple[float, ...] = field(default=(0.0,) * 12)
    fill_cap: tuple[float, ...] = field(default=(0.0,))
    fill_share: float = 0.4

    def split(self, node: Splitter, amount: float, t: Timestep) -> dict[str, float]:
        m = t.index % 12
        fill = 0.0
        if m in FILL_MONTHS and amount > self.need_below[m]:
            above_plant = max(amount - self.plant_need[m], 0.0)
            fill = min(self.fill_share * above_plant, self.fill_cap[m])
        return {"reservoir": fill, "lower_headworks": amount - fill}


@dataclass(frozen=True)
class LowerHeadworksPolicy(Strategy):
    """Lower headworks, below the reservoir: the power plant's intake first; then the lower canal takes its gross
    need, as far as the river above the reserve allows; the rest flows on."""

    __params__: ClassVar[tuple[str, ...]] = ("reserve_share",)
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {"reserve_share": LEVER_BOUNDS["reserve_share"]}

    natural: tuple[float, ...] = field(default=(0.0,) * 12)
    plant_need: tuple[float, ...] = field(default=(0.0,) * 12)
    canal_need: tuple[float, ...] = field(default=(0.0,) * 12)
    reserve_share: float = 0.15

    def split(self, node: Splitter, amount: float, t: Timestep) -> dict[str, float]:
        m = t.index % 12
        to_plant = min(amount, self.plant_need[m])
        rest = amount - to_plant
        take = min(self.canal_need[m], max(rest - self.reserve_share * self.natural[m], 0.0))
        return {"power_plant": to_plant, "lower_irrigation": take, "downstream": rest - take}


@dataclass(frozen=True)
class TopUpRelease(Strategy):
    """Reservoir release: in the release season a share of what is missing at the lower headworks for the power
    plant, the lower canal and the river reserve.

    In a month with a shortfall the weir does not fill, so the river at the lower headworks without a release is
    what arrives at the weir.
    """

    __params__: ClassVar[tuple[str, ...]] = ("release_share", "reserve_share")
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {
        "release_share": LEVER_BOUNDS["release_share"],
        "reserve_share": LEVER_BOUNDS["reserve_share"],
    }

    natural: tuple[float, ...] = field(default=(0.0,) * 12)
    city_need: tuple[float, ...] = field(default=(0.0,) * 12)
    transfers: tuple[float, ...] = field(default=(0.0,) * 12)
    canal_need: tuple[float, ...] = field(default=(0.0,) * 12)
    need_below: tuple[float, ...] = field(default=(0.0,) * 12)
    release_cap: tuple[float, ...] = field(default=(0.0,))
    release_share: float = 1.0
    reserve_share: float = 0.15

    def release(self, node: Storage, inflow: float, t: Timestep) -> float:
        m = t.index % 12
        if m not in RELEASE_MONTHS:
            return 0.0
        arriving = arriving_at_weir(
            self.reserve_share, self.natural, self.transfers, self.city_need, self.canal_need, m
        )
        shortfall = max(self.need_below[m] - arriving, 0.0)
        return min(self.release_share * shortfall, self.release_cap[m])


@dataclass(frozen=True)
class CanalSeepage:
    """A fixed share of the water entering the canal is lost for good before it reaches the fields."""

    fraction: float

    def calculate(self, reach: Reach, flow: float, t: Timestep) -> dict:
        return {SEEPAGE: self.fraction * flow}


# --- System ----------------------------------------------------------------------------------------------
class WarmupSystem(WaterSystem):
    """A TaqSim WaterSystem whose tunable vector is exactly the three game levers.

    The reserve share is a parameter of two rules (headworks, release); TaqSim v0.1.4 has no
    shared-parameter mechanism, so this subclass reports one entry per lever and rebuilds the system from a vector.
    """

    def __init__(self, year: str, levers: Levers) -> None:
        super().__init__(frequency=Frequency.MONTHLY)
        self.year = year
        self.levers = levers

    def param_schema(self) -> list[ParamSpec]:
        return [ParamSpec(path=LEVER_PATHS[name], value=getattr(self.levers, name)) for name in LEVER_PATHS]

    def param_bounds(self) -> dict[str, tuple[float, float]]:
        return {LEVER_PATHS[name]: LEVER_BOUNDS[name] for name in LEVER_PATHS}

    def bounds_vector(self) -> list[tuple[float, float]]:
        return [LEVER_BOUNDS[name] for name in LEVER_PATHS]

    def constraint_specs(self) -> list:
        return []

    def with_vector(self, vector: list[float]) -> "WarmupSystem":
        if len(vector) != len(LEVER_PATHS):
            raise ValueError(f"Vector length {len(vector)} does not match the {len(LEVER_PATHS)} levers")
        levers = Levers(**{name: float(v) for name, v in zip(LEVER_PATHS, vector, strict=True)})
        return build_system(self.year, levers)


def levers_from_parameters(parameters: dict[str, float]) -> Levers:
    """Map TaqSim's `Solution.parameters` back onto the game levers."""
    return Levers(**{name: float(parameters[path]) for name, path in LEVER_PATHS.items()})


@lru_cache(maxsize=8192)
def lower_drain_start(year: str, levers: Levers) -> float:
    """Content of the lower drain store on 1 October (Mm³): what repeats from year to year under this plan.

    What the lower canal takes depends on the reservoir, so it is read off a first run. The store itself feeds only
    the river below every off-take, so one run is enough: its content does not change what drains into it.
    """
    first = build_system(year, levers, lower_drain_initial=0.0)
    first.simulate(N_STEPS)
    return periodic_store(tuple(_monthly(first.nodes["lower_irrigation"], WaterOutput)), DRAINAGE_RECESSION)


def build_system(year: str, levers: Levers, lower_drain_initial: float | None = None) -> WarmupSystem:
    """Assemble the sixteen blocks and nineteen edges in TaqSim."""
    system = WarmupSystem(year, levers)
    river = natural(year)
    rule_inputs = {
        "natural": river,
        "city_need": CITY_MM3,
        "transfers": TRANSFERS_MM3,
        "canal_need": CANAL_NEED_MM3,
        "reserve_share": levers.reserve_share,
    }
    need_below = needed_below_weir(year, levers.reserve_share)
    if lower_drain_initial is None:
        lower_drain_initial = lower_drain_start(year, levers)

    system.add_node(Source(id="inflow", inflow=TimeSeries(values=list(river))))
    system.add_node(Reach(id="upper_river", routing_model=NoRouting(), loss_rule=NoReachLoss()))
    system.add_node(Splitter(id="headworks", split_policy=HeadworksPolicy(**rule_inputs)))
    system.add_node(Sink(id="transfers"))
    system.add_node(
        Splitter(
            id="weir",
            split_policy=WeirPolicy(
                need_below=need_below, plant_need=TPP_MM3, fill_cap=_cap(FILL_CAP_M3S), fill_share=levers.fill_share
            ),
        )
    )
    system.add_node(
        Storage(
            id="reservoir",
            capacity=RESERVOIR_CAPACITY_MM3,
            initial_storage=START_STORAGE_MM3,
            dead_storage=RESERVOIR_DEAD_MM3,
            release_policy=TopUpRelease(
                need_below=need_below,
                release_cap=_cap(RELEASE_CAP_M3S),
                release_share=levers.release_share,
                **rule_inputs,
            ),
            loss_rule=TableEvaporation(depth_mm=RESERVOIR_EVAPORATION_MM),
        )
    )
    # The ground under the fields: it takes the drain water and gives back a share of what it holds each month.
    system.add_node(
        Storage(
            id="drain_store",
            capacity=DRAIN_CAPACITY_MM3,
            initial_storage=drain_store_start(year, levers.reserve_share),
            release_policy=LinearRecession(recession=DRAINAGE_RECESSION),
            loss_rule=NoLoss(),
        )
    )
    system.add_node(
        Reach(
            id="main_canal",
            routing_model=NoRouting(),
            loss_rule=CanalSeepage(fraction=CANAL_LOSS),
            capacity=volume(CANAL_CAP_M3S, max(DAYS)),
        )
    )
    system.add_node(
        Demand(id="irrigation", requirement=TimeSeries(values=list(FIELD_NEED_MM3)), consumption_fraction=IRRIGATION_CF)
    )
    system.add_node(Demand(id="cities", requirement=TimeSeries(values=list(CITY_MM3)), consumption_fraction=CITY_CF))
    system.add_node(Demand(id="power_plant", requirement=TimeSeries(values=list(TPP_MM3)), consumption_fraction=TPP_CF))
    system.add_node(
        Splitter(
            id="lower_headworks",
            split_policy=LowerHeadworksPolicy(
                natural=river,
                plant_need=TPP_MM3,
                canal_need=LOWER_CANAL_NEED_MM3,
                reserve_share=levers.reserve_share,
            ),
        )
    )
    # The lower fields: of what the lower canal takes, the crops use ETA and a share is lost for good; the rest
    # drains into the lower store. The block books the loss with the crop use, as it has no canal reach of its own.
    system.add_node(
        Demand(
            id="lower_irrigation",
            requirement=TimeSeries(values=list(LOWER_CANAL_NEED_MM3)),
            consumption_fraction=1.0 - DRAIN_SHARE_OF_GROSS,
        )
    )
    system.add_node(
        Storage(
            id="lower_drain",
            capacity=DRAIN_CAPACITY_MM3,
            initial_storage=lower_drain_initial,
            release_policy=LinearRecession(recession=DRAINAGE_RECESSION),
            loss_rule=NoLoss(),
        )
    )
    system.add_node(
        Demand(
            id="downstream",
            requirement=TimeSeries(values=list(downstream_requirement(year))),
            consumption_fraction=0.0,
        )
    )
    system.add_node(Sink(id="sink"))
    for source, target in EDGES:
        system.add_edge(Edge(id=f"{source}_to_{target}", source=source, target=target))
    system.validate()
    return system


# --- Reading results -------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Outcome:
    monthly: dict[str, tuple[float, ...]]
    indicators: dict[str, float]


def _monthly(node, event_type: type, field_name: str = "amount") -> list[float]:
    totals = [0.0] * N_STEPS
    for event in node.events_of_type(event_type):
        totals[event.t] += getattr(event, field_name)
    return totals


def _edge_flows(system: WaterSystem) -> dict[str, list[float]]:
    flows: dict[str, list[float]] = {f"{s}_to_{t}": [0.0] * N_STEPS for s, t in EDGES}
    for node_id, node in system.nodes.items():
        if isinstance(node, Splitter):
            for event in node.events_of_type(WaterDistributed):
                flows[f"{node_id}_to_{event.target_id}"][event.t] += event.amount
        elif node.targets:
            for event in node.events_of_type(WaterOutput):
                flows[f"{node_id}_to_{node.targets[0]}"][event.t] += event.amount
    return flows


def _storage_path(system: WaterSystem, node_id: str = "reservoir") -> list[float]:
    reservoir = system.nodes[node_id]
    stored, lost, released = (
        _monthly(reservoir, WaterStored),
        _monthly(reservoir, WaterLost),
        _monthly(reservoir, WaterReleased),
    )
    level = reservoir.initial_storage
    path = []
    for s, loss, r in zip(stored, lost, released, strict=True):
        # Same operation order as Storage.update (store, lose, release) so the JavaScript twin matches exactly.
        level += s
        level -= loss
        level -= r
        path.append(level)
    return path


def read_outcome(system: WarmupSystem) -> Outcome:
    """Turn a simulated system's events into monthly series and indicators."""
    nodes = system.nodes
    river = natural(system.year)
    m: dict[str, list[float]] = {f"flow_{k}": v for k, v in _edge_flows(system).items()}
    m["inflow"] = list(river)
    m["eflow"] = list(eflow(system.year))
    m["downstream_users"] = list(DOWNSTREAM_USERS_MM3)
    m["storage"] = _storage_path(system)
    m["drain_store"] = _storage_path(system, "drain_store")
    m["drain_return"] = _monthly(nodes["drain_store"], WaterReleased)
    m["lower_drain_store"] = _storage_path(system, "lower_drain")
    m["lower_drain_return"] = _monthly(nodes["lower_drain"], WaterReleased)
    m["fill"] = _monthly(nodes["reservoir"], WaterStored)
    m["fill_refused"] = _monthly(nodes["reservoir"], WaterSpilled)
    m["evaporation"] = _monthly(nodes["reservoir"], WaterLost)
    m["release"] = _monthly(nodes["reservoir"], WaterReleased)
    m["canal_loss"] = _monthly(nodes["main_canal"], WaterLost)
    m["transfers"] = _monthly(nodes["transfers"], WaterReceived)
    m["outflow"] = _monthly(nodes["sink"], WaterReceived)

    retained_total = [0.0] * N_STEPS
    for node_id in DEMANDS:
        node = nodes[node_id]
        received = _monthly(node, WaterReceived)
        output = _monthly(node, WaterOutput)
        requirement = list(node.requirement.values)
        deficit = _monthly(node, DeficitRecorded, "deficit")
        m[f"received_{node_id}"] = received
        m[f"withdrawal_{node_id}"] = [min(a, r) for a, r in zip(received, requirement, strict=True)]
        m[f"requirement_{node_id}"] = requirement
        m[f"deficit_{node_id}"] = deficit
        m[f"output_{node_id}"] = output
        m[f"retained_{node_id}"] = [r - o for r, o in zip(received, output, strict=True)]
        for t in range(N_STEPS):
            retained_total[t] += m[f"retained_{node_id}"][t]
    # The irrigation block consumes the crop use; what it does not consume drains back to the river.
    m["crop_use"] = m["retained_irrigation"]
    m["crop_deficit"] = [c - u for c, u in zip(CROP_UPPER_MM3, m["crop_use"], strict=True)]
    # The lower block: of what its canal takes, the crops use ETA and CANAL_LOSS is lost for good.
    m["lower_crop_use"] = [ETA * w for w in m["withdrawal_lower_irrigation"]]
    m["lower_crop_deficit"] = [c - u for c, u in zip(CROP_LOWER_MM3, m["lower_crop_use"], strict=True)]
    m["lower_canal_loss"] = [CANAL_LOSS * w for w in m["withdrawal_lower_irrigation"]]
    m["tpp_output_fraction"] = [
        min(1.0, w / want) for w, want in zip(m["withdrawal_power_plant"], TPP_MM3, strict=True)
    ]
    m["energy_not_generated_gwh"] = [
        TPP_RIVER_COOLED_MW * TPP_CAPACITY_FACTOR * 24 * d * (1.0 - phi) / 1000.0
        for d, phi in zip(DAYS, m["tpp_output_fraction"], strict=True)
    ]
    m["outflow_m3s"] = [flow(v, d) for v, d in zip(m["outflow"], DAYS, strict=True)]

    initial = nodes["reservoir"].initial_storage
    drain_initial = nodes["drain_store"].initial_storage
    lower_drain_initial = nodes["lower_drain"].initial_storage
    ind: dict[str, float] = {
        "inflow": sum(river),
        "transfers": sum(m["transfers"]),
        "storage_initial": initial,
        "end_storage": m["storage"][-1],
        "storage_change": m["storage"][-1] - initial,
        "evaporation": sum(m["evaporation"]),
        "fill": sum(m["fill"]),
        "fill_refused": sum(m["fill_refused"]),
        "release": sum(m["release"]),
        "canal_loss": sum(m["canal_loss"]),
        "drain_in": sum(m["output_irrigation"]),
        "drain_return": sum(m["drain_return"]),
        "drain_store_initial": drain_initial,
        "drain_store_end": m["drain_store"][-1],
        "lower_drain_in": sum(m["output_lower_irrigation"]),
        "lower_drain_return": sum(m["lower_drain_return"]),
        "lower_drain_initial": lower_drain_initial,
        "lower_drain_end": m["lower_drain_store"][-1],
        "consumed": sum(retained_total),
        "outflow": sum(m["outflow"]),
        "outflow_min_m3s": min(m["outflow_m3s"]),
        "energy_not_generated_gwh": sum(m["energy_not_generated_gwh"]),
    }
    ind["balance_error"] = (
        ind["inflow"]
        + initial
        - ind["end_storage"]
        + drain_initial
        - ind["drain_store_end"]
        + lower_drain_initial
        - ind["lower_drain_end"]
        - ind["evaporation"]
        - ind["transfers"]
        - ind["canal_loss"]
        - sum(retained_total)
        - ind["outflow"]
    )

    def supply(node_id: str) -> float:
        req = sum(m[f"requirement_{node_id}"])
        return 100.0 * (req - sum(m[f"deficit_{node_id}"])) / req if req > 0 else 100.0

    ind["irrigation_supply"] = supply("irrigation")
    ind["irrigation_deficit"] = sum(m["crop_deficit"])
    ind["lower_irrigation_supply"] = supply("lower_irrigation")
    ind["lower_irrigation_deficit"] = sum(m["lower_crop_deficit"])
    ind["all_irrigation_supply"] = 100.0 * (sum(m["crop_use"]) + sum(m["lower_crop_use"])) / sum(CROP_MM3)
    ind["city_supply"] = supply("cities")
    ind["city_shortfall"] = sum(m["deficit_cities"])
    ind["city_months"] = float(sum(1 for s in m["deficit_cities"] if s <= 1e-9))
    ind["tpp_months"] = float(
        sum(1 for w, lo in zip(m["withdrawal_power_plant"], TPP_MIN_MM3, strict=True) if w >= lo - 1e-9)
    )
    ind["tpp_supply"] = supply("power_plant")
    ind["tpp_deficit"] = sum(m["deficit_power_plant"])
    ind["downstream_months"] = float(sum(1 for s in m["deficit_downstream"] if s <= 1e-9))
    ind["downstream_supply"] = supply("downstream")
    ind["downstream_short"] = sum(m["deficit_downstream"])
    return Outcome(monthly={k: tuple(v) for k, v in m.items()}, indicators=ind)


def evaluate(year: str, levers: Levers) -> Outcome:
    """Simulate one hydrological year with TaqSim and summarise the result."""
    system = build_system(year, levers)
    system.simulate(N_STEPS)
    return read_outcome(system)


# --- The complete lever grid -----------------------------------------------------------------------------
def non_dominated(points: np.ndarray, eps: float = 1e-9) -> np.ndarray:
    """Boolean mask of the rows no other row beats (at least as good everywhere, better somewhere; higher is better)."""
    keep = np.ones(len(points), dtype=bool)
    for i, p in enumerate(points):
        at_least = (points >= p - eps).all(axis=1)
        better = (points > p + eps).any(axis=1)
        keep[i] = not (at_least & better).any()
    return keep


def grid_indicators(year: str, grid: tuple[tuple[float, ...], ...] = LEVER_GRID) -> list[dict[str, float]]:
    """Indicators of every plan the sliders can set, in the order of the grid."""
    return [evaluate(year, Levers(*values)).indicators for values in grid]


# What the optimiser compares plans on: three shortfall volumes (lower is better) and the end storage.
OBJECTIVE_KEYS: tuple[tuple[str, float], ...] = (
    ("irrigation_deficit", -1.0),
    ("lower_irrigation_deficit", -1.0),
    ("downstream_short", -1.0),
    ("end_storage", 1.0),
)
AXIS_KEYS: tuple[tuple[str, float], ...] = tuple((a, 1.0) for a in AXES)


def unbeaten(indicators: list[dict[str, float]], keys: tuple[tuple[str, float], ...] = AXIS_KEYS) -> list[int]:
    """Positions of the plans that no other plan in the list beats on `keys` (name, +1 higher is better / -1 lower)."""
    points = np.array([[sign * ind[name] for name, sign in keys] for ind in indicators])
    return [int(i) for i in np.flatnonzero(non_dominated(points))]


def exact_front(year: str, grid: tuple[tuple[float, ...], ...] = LEVER_GRID) -> list[int]:
    """Positions in the grid of the plans that no other plan of the grid beats on the four axes of this year."""
    return unbeaten(grid_indicators(year, grid))


# --- Objectives ------------------------------------------------------------------------------------------
def _end_storage() -> Objective:
    return Objective(name="end_storage", direction="maximize", evaluate=lambda system: _storage_path(system)[-1])


OBJECTIVES = ("irrigation.deficit", "lower_irrigation.deficit", "downstream.deficit", "end_storage")


def objectives() -> list[Objective]:
    return [
        minimize_objectives.deficit("irrigation"),
        minimize_objectives.deficit("lower_irrigation"),
        minimize_objectives.deficit("downstream"),
        _end_storage(),
    ]


def optimise(year: str = "dry", pop_size: int = 100, generations: int = 100, seed: int = 42) -> list[Levers]:
    """NSGA-II over the three levers on one inflow year, as `taqsim.optimize` runs it: the plans it returns."""
    result = taqsim_optimize(
        system=build_system(year, Levers()),
        objectives=objectives(),
        timesteps=N_STEPS,
        pop_size=pop_size,
        generations=generations,
        seed=seed,
    )
    members = [levers_from_parameters(solution.parameters) for solution in result]
    logger.info("optimiser year=%s: %d plans", year, len(members))
    return members


def optimiser_check(year: str, indicators: list[dict[str, float]], pop_size: int, generations: int, seed: int) -> dict:
    """What the optimiser returns, measured against the complete grid on the optimiser's own objectives.

    `returned_unbeaten` counts the returned plans that no grid plan beats on the shortfall volumes and the end
    storage. The plans are then moved to the nearest slider steps; `unbeaten_on_objectives` counts how many of the
    moved plans no grid plan beats. The optimiser runs the model once per plan in the first population and once per
    plan in each generation. `levers` and `beaten` list the returned plans as they are, before they are moved, so
    that the page can draw them.
    """
    position = {values: i for i, values in enumerate(LEVER_GRID)}
    returned = optimise(year, pop_size, generations, seed)
    found = sorted({position[tuple(asdict(snap(lv)).values())] for lv in returned})
    best = set(unbeaten(indicators, OBJECTIVE_KEYS))
    grid_points = _objective_points(indicators)
    own_points = _objective_points([evaluate(year, lv).indicators for lv in returned])
    beaten = [_beaten_by_any(p, grid_points) for p in own_points]
    return {
        "runs": pop_size * (generations + 1),
        "returned": len(returned),
        "returned_unbeaten": sum(not b for b in beaten),
        "levers": [[round(v, 6) for v in asdict(lv).values()] for lv in returned],
        "beaten": beaten,
        "plans": len(found),
        "unbeaten_on_objectives": len(set(found) & best),
        "grid_unbeaten_on_objectives": len(best),
    }


def _objective_points(indicators: list[dict[str, float]]) -> np.ndarray:
    return np.array([[sign * ind[name] for name, sign in OBJECTIVE_KEYS] for ind in indicators])


def _beaten_by_any(point: np.ndarray, others: np.ndarray, eps: float = 1e-9) -> bool:
    return bool(((others >= point - eps).all(axis=1) & (others > point + eps).any(axis=1)).any())


CANONICAL_CASES: tuple[tuple[str, Levers], ...] = (
    ("dry", Levers()),
    ("median", Levers()),
    ("wet", Levers()),
    ("dry", Levers(reserve_share=0.0, fill_share=0.8, release_share=1.0)),
    ("dry", Levers(reserve_share=0.2, fill_share=0.4, release_share=1.0)),
    ("dry", Levers(reserve_share=0.4, fill_share=0.0, release_share=0.0)),
    ("wet", Levers(reserve_share=0.0, fill_share=0.8, release_share=0.5)),
)


def game_constants() -> dict:
    """Static inputs the browser model needs, in hydrological-year order."""
    return {
        "months": MONTHS,
        "days_in_month": DAYS,
        "years": {
            y: {
                "label": WORLD_LABELS[y],
                "natural_mm3": natural(y),
                "gauge_m3s": WORLD_GAUGE_M3S[y],
                "future": y in FUTURE_WORLDS,
            }
            for y in WORLDS
        },
        "climate": {"factors": CLIMATE_FACTORS, "source": CLIMATE_SOURCE, "base_year": "median"},
        "transfers_mm3": TRANSFERS_MM3,
        "crop_mm3": CROP_MM3,
        "crop_upper_mm3": CROP_UPPER_MM3,
        "crop_lower_mm3": CROP_LOWER_MM3,
        "lower_canal_cap_m3s": LOWER_CANAL_CAP_M3S,
        "eta_canal": ETA_CANAL,
        "eta_field": ETA_FIELD,
        "eta": ETA,
        "drainage_share": DRAINAGE_SHARE,
        "canal_loss": CANAL_LOSS,
        "drain_share_of_gross": DRAIN_SHARE_OF_GROSS,
        "drain_recession": DRAINAGE_RECESSION,
        "irrigation_cf": IRRIGATION_CF,
        "canal_cap_m3s": CANAL_CAP_M3S,
        "city_mm3": CITY_MM3,
        "city_cf": CITY_CF,
        "tpp": {
            "withdrawal_m3s": TPP_WITHDRAWAL_M3S,
            "consumptive_m3s": TPP_CONSUMPTIVE_M3S,
            "min_intake_m3s": TPP_MIN_INTAKE_M3S,
            "river_cooled_mw": TPP_RIVER_COOLED_MW,
            "capacity_factor": TPP_CAPACITY_FACTOR,
        },
        "eflow_share": EFLOW_SHARE,
        "downstream_users_mm3": DOWNSTREAM_USERS_MM3,
        "downstream_people_mm3": DOWNSTREAM_PEOPLE_MM3,
        "downstream_irrigation_mm3": DOWNSTREAM_IRRIGATION_MM3,
        "evaporation_mm": RESERVOIR_EVAPORATION_MM,
        "pan_evaporation_mm": EVAPORATION_MM,
        "pan_coefficient": PAN_COEFFICIENT,
        "va_volume_mm3": VA_VOLUME_MM3,
        "va_area_km2": VA_AREA_KM2,
        "reservoir": {
            "capacity": RESERVOIR_CAPACITY_MM3,
            "dead": RESERVOIR_DEAD_MM3,
            "initial": START_STORAGE_MM3,
            "fill_cap_m3s": FILL_CAP_M3S,
            "release_cap_m3s": RELEASE_CAP_M3S,
        },
        "fill_months": sorted(FILL_MONTHS),
        "release_months": sorted(RELEASE_MONTHS),
        "lever_bounds": LEVER_BOUNDS,
        "lever_steps": LEVER_STEPS,
        "lever_values": {name: lever_values(name) for name in LEVER_PATHS},
        "default_levers": asdict(Levers()),
        "axes": AXES,
        "objectives": OBJECTIVES,
        "edges": [f"{s}_to_{t}" for s, t in EDGES],
    }


def export_game_data(
    path: Path,
    n_reference_cases: int = 24,
    pop_size: int = 200,
    generations: int = 150,
    seed: int = 42,
    grid: tuple[tuple[float, ...], ...] = LEVER_GRID,
) -> None:
    """Write what the offline page needs: constants, reference cases for the JavaScript twin, and per year the
    exact set of unbeaten plans together with what the optimiser found of it."""
    rng = random.Random(seed)
    cases = list(CANONICAL_CASES)
    while len(cases) < n_reference_cases:
        cases.append((rng.choice(WORLDS), Levers(*rng.choice(LEVER_GRID))))
    reference_cases = []
    for year, levers in cases:
        outcome = evaluate(year, levers)
        reference_cases.append(
            {"year": year, "levers": asdict(levers), "indicators": outcome.indicators, "monthly": outcome.monthly}
        )
    fronts = {}
    for year in WORLDS:
        started = time.perf_counter()
        indicators = grid_indicators(year, grid)
        front = unbeaten(indicators)
        grid_time = time.perf_counter() - started
        started = time.perf_counter()
        optimiser = optimiser_check(year, indicators, pop_size, generations, seed) if grid is LEVER_GRID else None
        fronts[year] = {
            "year": year,
            "grid_size": len(grid),
            "front": front,
            "grid_time_s": round(grid_time, 1),
            "optimiser": optimiser,
            "optimiser_time_s": round(time.perf_counter() - started, 1),
        }
        logger.info("%s: %d of %d plans unbeaten (%.0f s)", year, len(front), len(grid), grid_time)
    data = {
        "meta": {
            "model": "warmup_game",
            "title": "The Zarafshan in sixteen blocks: a first model of the oasis",
            "taqsim_version": importlib.metadata.version("taqsim"),
            "twin_cases": len(reference_cases),
            "n_steps": N_STEPS,
            "time_frame": "one hydrological year, October to September, monthly steps",
            "units": {"volume": "Mm3 per month", "flow": "m3/s", "storage": "Mm3", "energy": "GWh"},
            "optimiser": {
                "algorithm": "NSGA-II (taqsim.optimize)",
                "pop_size": pop_size,
                "generations": generations,
                "seed": seed,
            },
        },
        "constants": game_constants(),
        "reference_cases": reference_cases,
        "fronts": fronts,
    }
    Path(path).write_text(json.dumps(data, separators=(",", ":")))
    logger.info("wrote %s", path)
