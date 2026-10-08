"""Zarafshan water-allocation trade-off game: reference model on TaqSim v0.1.4.

Reduced Zarafshan network (workshop/zarafshan_game/DESIGN.md §1-§2, with the 2026-10-04 audit changes recorded in
IMPLEMENTATION_NOTES.md): one hydrological year (Oct-Sep) in twelve monthly steps, run for a dry year (Oct 2020 -
Sep 2021), the 2017-2022 mean year and a wet year (Oct 2018 - Sep 2019). Volumes are Mm³ per month; monthly volume =
Q[m³/s] × 86 400 × days-in-month / 10⁶ (true calendar months).

    inflow -> Ravatkhoja HW -+-> Jizzakh transfer -> sink
                             +-> Kashkadarya transfer -> sink
                             +-> Samarkand canal irrigation -> drainage store --(delayed return)--+
                             +-> Samarkand M&I (own off-take, after the canals) --(return)--------+
                             +-> river -> Damkhoza -+-> Kattakurgan reservoir (top-up release) -+
                                                    +-> river --------------------------------> Narpay HW
                 Narpay HW -+-> Kattakurgan-command irrigation -> drainage store --(delayed return)--+
                            +-> river -> Navoi M&I -> Navoi industry -> Karmana intake
            Karmana intake -+-> Navoi TPP (existing units) --(return)--+
                            +-> Navoi TPP (new units, card C6) --------+
                            +-> river ---------------------------------> Karmana HW
                Karmana HW -+-> Navoi irrigation -> drainage store --(delayed return)--+
                            +-> river -------------------------------------------------> Navoi outflow (e-flow check)

The browser game re-implements these equations in JavaScript (workshop/zarafshan_game/game/model.js) and is
checked against the `reference_cases` written by `export_game_data`.
"""

import importlib.metadata
import itertools
import json
import logging
import random
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field, replace
from functools import lru_cache
from pathlib import Path
from typing import ClassVar

import numpy as np
from taqsim import Demand, Edge, Objective, Sink, Source, Splitter, Storage, Strategy, TimeSeries, WaterSystem
from taqsim import minimize as minimize_objectives
from taqsim import optimize as taqsim_optimize
from taqsim.common import EVAPORATION, ParamSpec
from taqsim.node import NoLoss
from taqsim.node.events import (
    DeficitRecorded,
    WaterConsumed,
    WaterDistributed,
    WaterGenerated,
    WaterLost,
    WaterOutput,
    WaterReceived,
    WaterReleased,
    WaterSpilled,
    WaterStored,
)
from taqsim.time import Frequency, Timestep

logger = logging.getLogger(__name__)

N_STEPS = 12
# Hydrological year: October to September.
MONTHS = ("Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep")
DAYS = (31, 30, 31, 31, 28, 31, 30, 31, 30, 31, 31, 30)
SECONDS_PER_DAY = 86_400
# Kattakurgan operating calendar, from the 2000-2022 storage record (research/kattakurgan_storage.md).
FILL_MONTHS = frozenset(range(1, 6))  # main fill November-March
FLOOD_FILL_MONTHS = frozenset(range(8, 11))  # optional flood fill June-August, surplus river only
RELEASE_MONTHS = frozenset({0, 1, 5, 6, 7, 8, 9, 10, 11})  # top-up release March-November
YEARS = ("dry", "median", "wet")


def _hydro(calendar: Iterable[float]) -> tuple[float, ...]:
    """Reorder a January-first series into the October-first hydrological year."""
    values = tuple(calendar)
    return values[9:] + values[:9]


# --- Data (data/ZRB_baseline/*, see research/zarafshan_data_sheet.md) ------------------------------------
# Ravatkhoja inflow, m³/s, October first. Dry and wet are true hydrological years (inflow_ravatkhoza.csv);
# "median" is the 2017-2022 mean of each calendar month (the key is kept for compatibility).
INFLOW_M3S: dict[str, tuple[float, ...]] = {
    "dry": (67.2, 55.9, 47.2, 47.5, 41.7, 41.6, 39.1, 106.8, 182.6, 222.7, 175.7, 127.0),
    "median": _hydro((43.88, 42.40, 45.36, 62.55, 138.26, 260.82, 366.65, 244.70, 132.29, 68.20, 54.58, 46.18)),
    "wet": (59.5, 48.2, 43.7, 42.3, 43.5, 44.1, 93.0, 133.1, 292.7, 562.5, 321.6, 136.4),
}
YEAR_LABELS = {
    "dry": "Dry year (Oct 2020 - Sep 2021)",
    "median": "Mean year (2017-2022 monthly means)",
    "wet": "Wet year (Oct 2018 - Sep 2019)",
}
# Monthly flow at the Navoi gauge (min_flow_navoi.csv), October first. The 2021 and 2022 rows of the file are
# identical fill values, so the dry-year series is observed for Oct-Dec 2020 only.
NAVOI_GAUGE_M3S: dict[str, tuple[float, ...]] = {
    "dry": (14.4, 13.6, 24.7, 27.1, 51.1, 35.3, 30.0, 19.4, 19.1, 21.4, 10.4, 14.1),
    "median": _hydro((24.19, 51.45, 26.99, 38.86, 22.78, 17.29, 22.04, 12.78, 12.2, 16.79, 20.27, 31.19)),
    "wet": (12.4, 19.0, 33.9, 17.0, 20.7, 9.1, 89.8, 44.8, 28.6, 60.4, 38.7, 11.2),
}
JIZZAKH_M3S = _hydro((2.32, 2.65, 1.86, 3.29, 5.37, 12.76, 18.61, 12.68, 6.07, 4.24, 2.22, 1.02))
KASHKADARYA_M3S = _hydro((0.0, 2.11, 6.32, 8.21, 12.13, 21.5, 32.77, 26.93, 4.57, 6.2, 7.47, 2.61))
# Crop requirement at the node (Mm³/month): Dargom + Mirzapay + Akkaradarya; Miankaltoss + Narpay; Karmanakonimex.
IRRIGATION_REQ_MM3: dict[str, tuple[float, ...]] = {
    "samarkand_irrigation": _hydro((0.0, 0.0, 5.8, 27.5, 77.3, 89.6, 115.7, 166.7, 111.9, 26.4, 0.0, 0.0)),
    "kattakurgan_irrigation": _hydro((0.0, 0.0, 3.3, 18.5, 38.6, 43.0, 83.0, 113.4, 66.8, 18.8, 0.0, 0.0)),
    "navoi_irrigation": _hydro((0.0, 0.0, 2.0, 9.1, 18.0, 15.1, 26.4, 38.7, 24.1, 8.4, 0.0, 0.0)),
}
# Narpay district alone: the only district the reservoir feeds in the source topology (demand CSV, Narpay_m3s).
NARPAY_REQ_MM3 = _hydro((0.0, 0.0, 1.0, 5.9, 12.1, 12.9, 36.1, 49.0, 27.3, 7.8, 0.0, 0.0))
IRRIGATION_NODES = tuple(IRRIGATION_REQ_MM3)
DRAINS = {
    "samarkand_irrigation": "drain_samarkand",
    "kattakurgan_irrigation": "drain_kattakurgan",
    "navoi_irrigation": "drain_navoi",
}
IRRIGATION_CAP_M3S = {"samarkand_irrigation": 370.0, "kattakurgan_irrigation": 180.0, "navoi_irrigation": 80.0}
# Pan evaporation at Kattakurgan (project lead, 2026-10-05), 2 337 mm a year. Open water loses less: the pan
# coefficient gives 1 402 mm a year, inside the 1 135-1 458 mm of Gapparov et al. 2019 (DESIGN.md §3). It is the
# default of the evaporation-scale setting. The warm-up game applies the same value once, to this raw series
# (warmup_game.PAN_COEFFICIENT; test_zarafshan_game.py keeps the two equal).
EVAPORATION_MM = _hydro((37.1, 37.9, 74.2, 130.7, 279.0, 418.3, 477.8, 387.1, 254.8, 139.0, 64.3, 36.3))
PAN_COEFFICIENT = 0.6
VA_VOLUME_MM3 = (0.0, 67.0, 133.0, 200.0, 267.0, 334.0, 400.0, 467.0, 534.0, 600.0, 667.0)
VA_AREA_KM2 = (0.0, 34.8, 40.0, 50.0, 54.2, 60.0, 60.0, 63.2, 70.0, 80.0, 100.0)
RESERVOIR_CAPACITY_MM3 = 667.0
RESERVOIR_DEAD_MM3 = 66.7
# Kattakurgan storage on 1 October, the single named starting value of the game: median of the 23 observed
# 30-September values 2000-2022 in the model's volume frame; quartiles 115 and 340 (research/kattakurgan_storage.md).
START_STORAGE_MM3 = 170.0
START_STORAGE_RANGE_MM3 = (115.0, 340.0)
RESERVOIR_INITIAL_MM3 = START_STORAGE_MM3  # older name, kept for the warm-up game
FILL_CAP_M3S = 100.0
RELEASE_CAP_M3S = 125.0
JIZZAKH_CAP_M3S = 45.0
KASHKADARYA_CAP_M3S = 60.0
POPULATION = {"samarkand_mi": 4_360_070, "navoi_mi": 1_108_595}
MUNICIPAL_RETURN = 0.7
INDUSTRY_CONSUMPTIVE = 0.5
TPP_WITHDRAWAL_M3S = 25.0
TPP_MIN_INTAKE_M3S = 15.0
TPP_CAPACITY_MW = 2151.0
TPP_CAPACITY_FACTOR = 0.6
# Units whose output depends on the river intake: the 1 200 MW of steam units with once-through cooling.
TPP_RIVER_COOLED_MW = 1200.0
TPP_NEW_UNITS_MW = 1300.0
# New combined-cycle units (card C6): wet cooling towers are the documented type; once-through is the stress case.
TPP_NEW_TOWER_M3S = (0.2, 0.17)  # withdrawal, consumption
TPP_NEW_ONCE_THROUGH_M3S = (29.0, 0.2)
# Drainage: a recoverable share of irrigation conveyance and field losses returns to the river through a
# linear store. Both values are calibrated against the Navoi gauge (IMPLEMENTATION_NOTES.md).
DRAINAGE_SHARE = 0.7  # upper end of the allowed range 0.2-0.7; the calibration did not meet its tolerance
DRAINAGE_RECESSION = 0.1  # share of the store released per month
DRAIN_CAPACITY_MM3 = 1.0e6


@dataclass(frozen=True)
class Settings:
    """Assumption-panel settings; not levers, not cards."""

    evaporation_scale: float = PAN_COEFFICIENT  # 1.0 is the pan series unchanged
    tpp_consumptive_m3s: float = 8.0
    municipal_lcd: float = 150.0
    industry_m3s: float = 3.0
    drainage_share: float = DRAINAGE_SHARE
    start_storage: float = START_STORAGE_MM3
    expansion_once_through: float = 0.0  # >= 0.5: the C6 units use once-through cooling


SETTING_BOUNDS: dict[str, tuple[float, float]] = {
    "evaporation_scale": (0.5, 1.0),
    "tpp_consumptive_m3s": (1.0, 10.0),
    "municipal_lcd": (100.0, 250.0),
    "industry_m3s": (0.0, 10.0),
    "drainage_share": (0.2, 0.7),
    "start_storage": START_STORAGE_RANGE_MM3,
    "expansion_once_through": (0.0, 1.0),
}


@dataclass(frozen=True)
class Levers:
    """Player decisions. `tpp_priority` >= 0.5 means the plant takes water before the reserve check."""

    canal_supply: float = 1.0  # L1 share of the Samarkand canals' gross need the headworks tries to deliver
    transfer_share: float = 1.0  # L2 share of the agreed transfers delivered
    fill_share: float = 0.4  # L3 share of the spare winter river diverted into Kattakurgan
    release_share: float = 1.0  # L4 share of the command area's shortfall the reservoir covers
    tpp_priority: float = 1.0  # L5
    reserve_share: float = 0.2  # L6 share of natural inflow every off-take leaves in the river


LEVER_BOUNDS: dict[str, tuple[float, float]] = {
    "canal_supply": (0.5, 1.0),
    "transfer_share": (0.0, 1.0),
    "fill_share": (0.0, 0.8),
    "release_share": (0.0, 1.0),
    "tpp_priority": (0.0, 1.0),
    "reserve_share": (0.0, 0.4),
}
# Where TaqSim sees each lever (the reserve share is repeated on several policies; see ZarafshanSystem).
LEVER_PATHS: dict[str, str] = {
    "canal_supply": "ravatkhoja_hw.split_policy.canal_supply",
    "transfer_share": "ravatkhoja_hw.split_policy.transfer_share",
    "fill_share": "damkhoza.split_policy.fill_share",
    "release_share": "kattakurgan.release_policy.release_share",
    "tpp_priority": "karmana_intake.split_policy.tpp_priority",
    "reserve_share": "ravatkhoja_hw.split_policy.reserve_share",
}
# Operations assumed for the comparison with the Navoi gauge: no e-flow reserve was operated historically.
# The fill share is the lever step whose modelled winter rise of Kattakurgan in the mean year (446 Mm³, measured
# with `storage_cycle`) is closest to the observed median (439 Mm³, research/kattakurgan_storage.md:113).
HISTORICAL_PLAN = Levers(fill_share=0.7, reserve_share=0.0)


@dataclass(frozen=True)
class Card:
    id: str
    name: str
    narrative: str
    changes: str


CARDS: dict[str, Card] = {
    "C1": Card(
        "C1",
        "Growing cities",
        "The Samarkand and Navoi regions grow by a quarter by 2040. Navoi industry doubles.",
        "municipal demand × 1.25; Navoi industry × 2",
    ),
    "C2": Card(
        "C2",
        "Irrigation expansion",
        "The irrigated area grows by 15 %.",
        "crop requirement × 1.15 in all three irrigation groups",
    ),
    "C3": Card(
        "C3",
        "Water-saving programme",
        "Canal lining and drip irrigation reach the 2028 national targets.",
        "conveyance efficiency 0.65 → 0.80; field efficiency 0.75 → 0.85; less water is lost, so less drainage "
        "water returns to the river",
    ),
    "C4": Card(
        "C4",
        "More storage",
        "Kattakurgan reservoir is raised by 300 Mm³.",
        "capacity 667 → 967 Mm³; fill capacity unchanged (100 m³/s); the fill months do not change. Under the "
        "starting plan this changes no result in any of the three years: it changes results only if the reservoir "
        "would otherwise be full (a high fill share, lever L3, in the mean or wet year)",
    ),
    "C5": Card(
        "C5",
        "Earlier, lower snowmelt",
        "Glaciers shrink: 15 % less water in every month, and a fifth of the June to August flow arrives in "
        "April and May instead.",
        "inflow × 0.85 every month; 20 % of the Jun-Aug volume moved equally into Apr-May",
    ),
    "C6": Card(
        "C6",
        "Power plant expansion",
        "Two new combined-cycle units (1 300 MW) start operating. They are cooled by wet cooling towers.",
        "new units: + 0.2 m³/s withdrawal, + 0.17 m³/s consumption, on top of the existing 25 and 8 m³/s; with "
        "the setting 'once-through cooling' the new units withdraw 29 m³/s instead. With cooling towers the new units "
        "change almost nothing in this model: irrigation supply by at most 0.1 points and the outflow to Bukhara by "
        "4 to 5 Mm³ a year less. With once-through cooling the mean and wet year also end with 50 to 60 Mm³ less in "
        "the reservoir, because less flood water is stored",
    ),
    "C7": Card(
        "C7",
        "Stricter environmental-flow rule",
        "The inspectorate sets the required flow to Bukhara at 30 % of the natural flow.",
        "environmental-flow target 0.20 → 0.30 of natural monthly inflow; the reserve lever L6 stays with the players",
    ),
    "C8": Card(
        "C8",
        "Ageing reservoir",
        "Sediment has filled a tenth of Kattakurgan reservoir.",
        "capacity × 0.90 (600 Mm³); dead storage unchanged. It changes results only if the reservoir would hold "
        "more than 600 Mm³. Under the starting plan that happens in the wet year only: the reservoir is full in "
        "July, ends the year 21 Mm³ lower and the outflow to Bukhara is 25 Mm³ higher. With a high fill share "
        "(lever L3) it also happens in the mean year",
    ),
}


@dataclass(frozen=True)
class World:
    """Everything the model needs after settings, cards and the year have been resolved."""

    year: str
    natural: tuple[float, ...]  # Mm³ per month at Ravatkhoja
    municipal_factor: float
    municipal_lcd: float
    industry_m3s: float
    area_factor: float
    eta_c: float
    eta_f: float
    drainage_share: float
    drainage_recession: float
    capacity: float
    start_storage: float
    evaporation_scale: float
    tpp_consumptive_m3s: float
    tpp_new_withdrawal_m3s: float
    tpp_new_consumptive_m3s: float
    tpp_new_mw: float
    eflow_target: float


def volume(q_m3s: float, days: int) -> float:
    """Monthly volume in Mm³ from a flow in m³/s."""
    return q_m3s * SECONDS_PER_DAY * days / 1e6


def flow(volume_mm3: float, days: int) -> float:
    """Mean flow in m³/s from a monthly volume in Mm³."""
    return volume_mm3 * 1e6 / (SECONDS_PER_DAY * days)


def natural_inflow(year: str, cards: Iterable[str]) -> tuple[float, ...]:
    """Natural monthly inflow at Ravatkhoja (Mm³), after the snowmelt card if drawn."""
    if year not in INFLOW_M3S:
        raise ValueError(f"unknown year {year!r}; choose one of {YEARS}")
    series = [volume(q, d) for q, d in zip(INFLOW_M3S[year], DAYS, strict=True)]
    if "C5" in set(cards):
        series = [v * 0.85 for v in series]
        summer = (8, 9, 10)  # Jun, Jul, Aug
        moved = 0.2 * (series[8] + series[9] + series[10])
        for m in summer:
            series[m] = series[m] * 0.8
        series[6] = series[6] + moved / 2  # Apr
        series[7] = series[7] + moved / 2  # May
    return tuple(series)


def resolve(settings: Settings, cards: Iterable[str], year: str) -> World:
    """Apply the scenario cards (in C1..C8 order) to the settings for one inflow year."""
    active = set(cards)
    unknown = active - set(CARDS)
    if unknown:
        raise ValueError(f"unknown card(s) {sorted(unknown)}; choose from {sorted(CARDS)}")
    capacity = RESERVOIR_CAPACITY_MM3
    if "C4" in active:
        capacity = capacity + 300.0
    if "C8" in active:
        capacity = capacity * 0.9
    new_units = TPP_NEW_ONCE_THROUGH_M3S if settings.expansion_once_through >= 0.5 else TPP_NEW_TOWER_M3S
    expanded = "C6" in active
    return World(
        year=year,
        natural=natural_inflow(year, active),
        municipal_factor=1.25 if "C1" in active else 1.0,
        municipal_lcd=settings.municipal_lcd,
        industry_m3s=settings.industry_m3s * 2.0 if "C1" in active else settings.industry_m3s,
        area_factor=1.15 if "C2" in active else 1.0,
        eta_c=0.80 if "C3" in active else 0.65,
        eta_f=0.85 if "C3" in active else 0.75,
        drainage_share=settings.drainage_share,
        drainage_recession=DRAINAGE_RECESSION,
        capacity=capacity,
        start_storage=min(settings.start_storage, capacity),
        evaporation_scale=settings.evaporation_scale,
        tpp_consumptive_m3s=settings.tpp_consumptive_m3s,
        tpp_new_withdrawal_m3s=new_units[0] if expanded else 0.0,
        tpp_new_consumptive_m3s=new_units[1] if expanded else 0.0,
        tpp_new_mw=TPP_NEW_UNITS_MW if expanded else 0.0,
        eflow_target=0.30 if "C7" in active else 0.20,
    )


def interpolate(x: float, xs: tuple[float, ...], ys: tuple[float, ...]) -> float:
    """Piecewise-linear interpolation, clamped at both ends (same arithmetic as the JavaScript twin)."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    i = 0
    while x >= xs[i + 1]:
        i += 1
    return ys[i] + (ys[i + 1] - ys[i]) * (x - xs[i]) / (xs[i + 1] - xs[i])


def reservoir_area(volume_mm3: float) -> float:
    """Kattakurgan surface area (km²); above the table's top the last segment is extended (assumed, card C4)."""
    top = VA_VOLUME_MM3[-1]
    if volume_mm3 <= top:
        return interpolate(volume_mm3, VA_VOLUME_MM3, VA_AREA_KM2)
    slope = (VA_AREA_KM2[-1] - VA_AREA_KM2[-2]) / (VA_VOLUME_MM3[-1] - VA_VOLUME_MM3[-2])
    return VA_AREA_KM2[-1] + slope * (volume_mm3 - top)


def reserve_take(want: float, cap: float, remaining: float, credit: float, reserve: float, rho: float) -> float:
    """Largest withdrawal that leaves the e-flow reserve in the river once this user's return has rejoined it.

    `credit` is the river water that will be downstream of this headworks if the user takes nothing
    (water still at the headworks plus returns already committed in the same month).
    """
    if rho >= 1.0:  # a user that returns everything never lowers the river
        return min(want, cap, remaining)
    x_max = max(credit - reserve, 0.0) / (1.0 - rho)
    return min(want, cap, remaining, x_max)


# --- Requirements ----------------------------------------------------------------------------------------
def municipal_requirement(world: World, node_id: str) -> tuple[float, ...]:
    """Gross municipal supply (Mm³/month) = population × litres per capita per day × days."""
    return tuple(POPULATION[node_id] * world.municipal_lcd * d * 1e-9 * world.municipal_factor for d in DAYS)


def irrigation_requirement(world: World, node_id: str) -> tuple[float, ...]:
    """Crop requirement at the node (Mm³/month), scaled by the irrigated-area factor."""
    return tuple(r * world.area_factor for r in IRRIGATION_REQ_MM3[node_id])


def irrigation_gross(world: World, node_id: str) -> tuple[float, ...]:
    """Gross diversion needed at the headworks: requirement / (conveyance × field efficiency)."""
    eff = world.eta_c * world.eta_f
    return tuple(r / eff for r in irrigation_requirement(world, node_id))


def narpay_gross(world: World) -> tuple[float, ...]:
    """Gross need of the Narpay district alone: the most the reservoir may be asked to cover in a month."""
    eff = world.eta_c * world.eta_f
    return tuple(r * world.area_factor / eff for r in NARPAY_REQ_MM3)


def transfer_requirement(node_id: str) -> tuple[float, ...]:
    series = {"jizzakh": JIZZAKH_M3S, "kashkadarya": KASHKADARYA_M3S}[node_id]
    return tuple(volume(q, d) for q, d in zip(series, DAYS, strict=True))


def eflow_target(world: World) -> tuple[float, ...]:
    return tuple(world.eflow_target * q for q in world.natural)


def _cap(q_m3s: float) -> tuple[float, ...]:
    return tuple(volume(q_m3s, d) for d in DAYS)


# --- Strategies ------------------------------------------------------------------------------------------
class RiverGauge:
    """What the operators can read this month: the river continuing past Damkhoza and the reservoir release.

    TaqSim policies see only their own node; the top-up release needs the river beside the reservoir, so the
    Damkhoza and Kattakurgan policies of one system share this small record (written and read within a month).
    """

    __slots__ = ("release", "release_t", "river", "river_t")

    def __init__(self) -> None:
        self.river_t = -1
        self.river = 0.0
        self.release_t = -1
        self.release = 0.0

    def river_at(self, t: int) -> float:
        return self.river if self.river_t == t else 0.0

    def release_at(self, t: int) -> float:
        return self.release if self.release_t == t else 0.0


@dataclass(frozen=True)
class RavatkhojaPolicy(Strategy):
    """Ravatkhoja headworks: transfers, then the Samarkand canals (Dargom system), each limited by the e-flow
    reserve; then Samarkand M&I as its own off-take, exempt from the reserve; the rest stays in the river."""

    __params__: ClassVar[tuple[str, ...]] = ("canal_supply", "transfer_share", "reserve_share")
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {
        "canal_supply": LEVER_BOUNDS["canal_supply"],
        "transfer_share": LEVER_BOUNDS["transfer_share"],
        "reserve_share": LEVER_BOUNDS["reserve_share"],
    }

    natural: tuple[float, ...] = field(default=(0.0,))
    jizzakh_want: tuple[float, ...] = field(default=(0.0,))
    kashkadarya_want: tuple[float, ...] = field(default=(0.0,))
    irrigation_gross: tuple[float, ...] = field(default=(0.0,))
    city_want: tuple[float, ...] = field(default=(0.0,))
    jizzakh_cap: tuple[float, ...] = field(default=(0.0,))
    kashkadarya_cap: tuple[float, ...] = field(default=(0.0,))
    irrigation_cap: tuple[float, ...] = field(default=(0.0,))
    canal_supply: float = 1.0
    transfer_share: float = 1.0
    reserve_share: float = 0.2

    def split(self, node: Splitter, amount: float, t: Timestep) -> dict[str, float]:
        m = t.index % 12
        reserve = self.reserve_share * self.natural[m]
        remaining = amount
        jizzakh = reserve_take(
            self.transfer_share * self.jizzakh_want[m], self.jizzakh_cap[m], remaining, remaining, reserve, 0.0
        )
        remaining -= jizzakh
        kashkadarya = reserve_take(
            self.transfer_share * self.kashkadarya_want[m], self.kashkadarya_cap[m], remaining, remaining, reserve, 0.0
        )
        remaining -= kashkadarya
        irrigation = reserve_take(
            self.canal_supply * self.irrigation_gross[m], self.irrigation_cap[m], remaining, remaining, reserve, 0.0
        )
        remaining -= irrigation
        city = min(remaining, self.city_want[m])
        remaining -= city
        return {
            "jizzakh": jizzakh,
            "kashkadarya": kashkadarya,
            "samarkand_irrigation": irrigation,
            "samarkand_mi": city,
            "damkhoza": remaining,
        }


@dataclass(frozen=True)
class DamkhozaPolicy(Strategy):
    """Damkhoza junction: divert a share of the spare river into the Kattakurgan feeder.

    November-March (main fill): spare = river above the e-flow reserve and above what the reservoir's own command
    area needs this month. June-August (flood fill): spare = river above the reserve and above every downstream
    need (command area, Navoi irrigation, power plant, Navoi city and industry). No fill in other months.
    """

    __params__: ClassVar[tuple[str, ...]] = ("fill_share", "reserve_share")
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {
        "fill_share": LEVER_BOUNDS["fill_share"],
        "reserve_share": LEVER_BOUNDS["reserve_share"],
    }

    natural: tuple[float, ...] = field(default=(0.0,))
    command_need: tuple[float, ...] = field(default=(0.0,))
    downstream_need: tuple[float, ...] = field(default=(0.0,))
    fill_cap: tuple[float, ...] = field(default=(0.0,))
    gauge: RiverGauge = field(default_factory=RiverGauge, compare=False)
    fill_share: float = 0.4
    reserve_share: float = 0.2

    def split(self, node: Splitter, amount: float, t: Timestep) -> dict[str, float]:
        m = t.index % 12
        fill = 0.0
        if m in FILL_MONTHS or m in FLOOD_FILL_MONTHS:
            reserve = self.reserve_share * self.natural[m]
            needs = self.command_need[m] if m in FILL_MONTHS else self.downstream_need[m]
            spare = max(amount - reserve - needs, 0.0)
            fill = min(self.fill_share * spare, self.fill_cap[m], amount)
        self.gauge.river = amount - fill
        self.gauge.river_t = t.index
        return {"kattakurgan": fill, "kattakurgan_hw": amount - fill}


@dataclass(frozen=True)
class TopUpRelease(Strategy):
    """Kattakurgan release: only what the river cannot supply to the command area.

    Shortfall = command need - river above the reserve at Narpay HW; the reservoir covers `release_share` of it,
    at most the Narpay district's own gross need, within the outlet capacity and down to dead storage.
    """

    __params__: ClassVar[tuple[str, ...]] = ("release_share", "reserve_share")
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {
        "release_share": LEVER_BOUNDS["release_share"],
        "reserve_share": LEVER_BOUNDS["reserve_share"],
    }

    natural: tuple[float, ...] = field(default=(0.0,))
    command_need: tuple[float, ...] = field(default=(0.0,))
    narpay_gross: tuple[float, ...] = field(default=(0.0,))
    release_cap: tuple[float, ...] = field(default=(0.0,))
    gauge: RiverGauge = field(default_factory=RiverGauge, compare=False)
    release_share: float = 1.0
    reserve_share: float = 0.2

    def release(self, node: Storage, inflow: float, t: Timestep) -> float:
        m = t.index % 12
        target = 0.0
        if m in RELEASE_MONTHS:
            reserve = self.reserve_share * self.natural[m]
            from_river = max(self.gauge.river_at(t.index) - reserve, 0.0)
            shortfall = max(self.command_need[m] - from_river, 0.0)
            target = min(self.release_share * min(shortfall, self.narpay_gross[m]), self.release_cap[m])
        actual = max(0.0, min(target, max(node.storage - node.dead_storage, 0.0)))
        self.gauge.release = actual
        self.gauge.release_t = t.index
        return actual


@dataclass(frozen=True)
class CommandOfftakePolicy(Strategy):
    """Narpay headworks: the command area takes the reservoir release in full and river water above the reserve."""

    __params__: ClassVar[tuple[str, ...]] = ("reserve_share",)
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {"reserve_share": LEVER_BOUNDS["reserve_share"]}

    natural: tuple[float, ...] = field(default=(0.0,))
    gross: tuple[float, ...] = field(default=(0.0,))
    cap: tuple[float, ...] = field(default=(0.0,))
    gauge: RiverGauge = field(default_factory=RiverGauge, compare=False)
    reserve_share: float = 0.2

    def split(self, node: Splitter, amount: float, t: Timestep) -> dict[str, float]:
        m = t.index % 12
        reserve = self.reserve_share * self.natural[m]
        release = self.gauge.release_at(t.index)
        take = min(self.gross[m], self.cap[m], amount, release + max(amount - release - reserve, 0.0))
        return {"kattakurgan_irrigation": take, "navoi_mi": amount - take}


@dataclass(frozen=True)
class OfftakePolicy(Strategy):
    """A headworks with one irrigation off-take (Karmana) limited by the reserve."""

    __params__: ClassVar[tuple[str, ...]] = ("reserve_share",)
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {"reserve_share": LEVER_BOUNDS["reserve_share"]}

    natural: tuple[float, ...] = field(default=(0.0,))
    gross: tuple[float, ...] = field(default=(0.0,))
    cap: tuple[float, ...] = field(default=(0.0,))
    offtake_id: str = ""
    river_id: str = ""
    reserve_share: float = 0.2

    def split(self, node: Splitter, amount: float, t: Timestep) -> dict[str, float]:
        m = t.index % 12
        reserve = self.reserve_share * self.natural[m]
        take = reserve_take(self.gross[m], self.cap[m], amount, amount, reserve, 0.0)
        return {self.offtake_id: take, self.river_id: amount - take}


@dataclass(frozen=True)
class IntakePolicy(Strategy):
    """Karmana power-plant intake: existing units first, then the new units, before or after the reserve check."""

    __params__: ClassVar[tuple[str, ...]] = ("tpp_priority", "reserve_share")
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {
        "tpp_priority": LEVER_BOUNDS["tpp_priority"],
        "reserve_share": LEVER_BOUNDS["reserve_share"],
    }

    natural: tuple[float, ...] = field(default=(0.0,))
    want: tuple[float, ...] = field(default=(0.0,))
    want_new: tuple[float, ...] = field(default=(0.0,))
    tpp_return: float = 0.68
    new_return: float = 0.0
    tpp_priority: float = 1.0
    reserve_share: float = 0.2

    def split(self, node: Splitter, amount: float, t: Timestep) -> dict[str, float]:
        m = t.index % 12
        reserve = self.reserve_share * self.natural[m]
        if self.tpp_priority >= 0.5:
            take = min(amount, self.want[m])
            remaining = amount - take
            new = min(remaining, self.want_new[m])
        else:
            take = reserve_take(self.want[m], self.want[m], amount, amount, reserve, self.tpp_return)
            remaining = amount - take
            credit = remaining + self.tpp_return * take
            new = reserve_take(self.want_new[m], self.want_new[m], remaining, credit, reserve, self.new_return)
        return {"navoi_tpp": take, "navoi_tpp_new": new, "karmana_hw": remaining - new}


@dataclass(frozen=True)
class LinearRecession:
    """Drainage store: each month a fixed share of what is stored returns to the river."""

    recession: float

    def release(self, node: Storage, inflow: float, t: Timestep) -> float:
        return self.recession * node.storage


@dataclass(frozen=True)
class TableEvaporation:
    """Open-water evaporation = depth [mm] × surface area from the volume-area table [km²] × 10⁻³ (Mm³)."""

    depth_mm: tuple[float, ...]

    def calculate(self, node: Storage, t: Timestep) -> dict:
        return {EVAPORATION: self.depth_mm[t.index % 12] * reservoir_area(node.storage) * 1e-3}


# --- System ----------------------------------------------------------------------------------------------
EDGES: tuple[tuple[str, str], ...] = (
    ("inflow", "ravatkhoja_hw"),
    ("ravatkhoja_hw", "jizzakh"),
    ("ravatkhoja_hw", "kashkadarya"),
    ("ravatkhoja_hw", "samarkand_irrigation"),
    ("ravatkhoja_hw", "samarkand_mi"),
    ("ravatkhoja_hw", "damkhoza"),
    ("jizzakh", "sink_jizzakh"),
    ("kashkadarya", "sink_kashkadarya"),
    ("samarkand_irrigation", "drain_samarkand"),
    ("drain_samarkand", "damkhoza"),
    ("samarkand_mi", "damkhoza"),
    ("damkhoza", "kattakurgan"),
    ("damkhoza", "kattakurgan_hw"),
    ("kattakurgan", "kattakurgan_hw"),
    ("kattakurgan_hw", "kattakurgan_irrigation"),
    ("kattakurgan_hw", "navoi_mi"),
    ("kattakurgan_irrigation", "drain_kattakurgan"),
    ("drain_kattakurgan", "navoi_mi"),
    ("navoi_mi", "navoi_industry"),
    ("navoi_industry", "karmana_intake"),
    ("karmana_intake", "navoi_tpp"),
    ("karmana_intake", "navoi_tpp_new"),
    ("karmana_intake", "karmana_hw"),
    ("navoi_tpp", "karmana_hw"),
    ("navoi_tpp_new", "karmana_hw"),
    ("karmana_hw", "navoi_irrigation"),
    ("karmana_hw", "eflow_navoi"),
    ("navoi_irrigation", "drain_navoi"),
    ("drain_navoi", "eflow_navoi"),
    ("eflow_navoi", "bukhara"),
)


class ZarafshanSystem(WaterSystem):
    """A TaqSim WaterSystem whose tunable vector is exactly the six game levers.

    The e-flow reserve share (L6) is a parameter of several policies; TaqSim v0.1.4 has no shared-parameter
    mechanism, so the base schema would expose independent copies. This subclass reports one entry per lever
    (`LEVER_PATHS`) and rebuilds the whole system from a lever vector, which is what NSGA-II needs.
    """

    def __init__(self, world: World, levers: Levers) -> None:
        super().__init__(frequency=Frequency.MONTHLY)
        self.world = world
        self.levers = levers

    def param_schema(self) -> list[ParamSpec]:
        return [ParamSpec(path=LEVER_PATHS[name], value=getattr(self.levers, name)) for name in LEVER_PATHS]

    def param_bounds(self) -> dict[str, tuple[float, float]]:
        return {LEVER_PATHS[name]: LEVER_BOUNDS[name] for name in LEVER_PATHS}

    def bounds_vector(self) -> list[tuple[float, float]]:
        return [LEVER_BOUNDS[name] for name in LEVER_PATHS]

    def constraint_specs(self) -> list:
        return []

    def with_vector(self, vector: list[float]) -> "ZarafshanSystem":
        if len(vector) != len(LEVER_PATHS):
            raise ValueError(f"Vector length {len(vector)} does not match the {len(LEVER_PATHS)} levers")
        levers = Levers(**{name: float(v) for name, v in zip(LEVER_PATHS, vector, strict=True)})
        return build_system(self.world, levers)


def levers_from_parameters(parameters: dict[str, float]) -> Levers:
    """Map TaqSim's `Solution.parameters` back onto the game levers (the TPP priority is rounded to 0/1)."""
    values = {name: float(parameters[path]) for name, path in LEVER_PATHS.items()}
    values["tpp_priority"] = 1.0 if values["tpp_priority"] >= 0.5 else 0.0
    return Levers(**values)


def irrigation_efficiencies(world: World) -> tuple[float, float, float]:
    """(crop share η, TaqSim efficiency η + φ(1-η), TaqSim consumption fraction) of an irrigation node.

    Of each unit diverted, η = η_c·η_f reaches the crop and is consumed, φ(1-η) is recoverable loss that drains
    back to the river through the drainage store, and (1-φ)(1-η) is lost for good. TaqSim's Demand returns flow
    out of *delivered* water, so the node is given efficiency η + φ(1-η) and consumption fraction η / that.
    """
    eta = world.eta_c * world.eta_f
    served = eta + world.drainage_share * (1.0 - eta)
    return eta, served, eta / served


def _periodic_store(inputs: Iterable[float], recession: float) -> float:
    """Start content of a linear store that ends the year where it started, for these monthly inputs."""
    keep = 1.0 - recession
    carried = 0.0
    decay = 1.0
    for value in inputs:
        carried = (carried + value) * keep
        decay = decay * keep
    return carried / (1.0 - decay)


@lru_cache(maxsize=512)
def drainage_initial(world: World) -> tuple[float, ...]:
    """Drainage-store contents on 1 October: periodic under the starting plan (two fixed-point passes)."""
    start = (0.0,) * len(DRAINS)
    for _ in range(2):
        system = _assemble(world, Levers(), start)
        system.simulate(N_STEPS)
        start = tuple(
            _periodic_store(_monthly(system.nodes[drain], WaterReceived), world.drainage_recession)
            for drain in DRAINS.values()
        )
    return start


def build_system(world: World, levers: Levers) -> ZarafshanSystem:
    """Assemble the reduced Zarafshan network in TaqSim."""
    return _assemble(world, levers, drainage_initial(world))


def _assemble(world: World, levers: Levers, drain_start: tuple[float, ...]) -> ZarafshanSystem:
    system = ZarafshanSystem(world, levers)
    eta, served, irrigation_cf = irrigation_efficiencies(world)
    tpp_want = _cap(TPP_WITHDRAWAL_M3S)
    tpp_cf = world.tpp_consumptive_m3s / TPP_WITHDRAWAL_M3S
    new_want = _cap(world.tpp_new_withdrawal_m3s)
    new_cf = world.tpp_new_consumptive_m3s / world.tpp_new_withdrawal_m3s if world.tpp_new_withdrawal_m3s > 0 else 0.0
    gross = {node_id: irrigation_gross(world, node_id) for node_id in IRRIGATION_NODES}
    command_cap = _cap(IRRIGATION_CAP_M3S["kattakurgan_irrigation"])
    command_need = tuple(min(g, c) for g, c in zip(gross["kattakurgan_irrigation"], command_cap, strict=True))
    navoi_cap = _cap(IRRIGATION_CAP_M3S["navoi_irrigation"])
    navoi_city = municipal_requirement(world, "navoi_mi")
    industry = _cap(world.industry_m3s)
    downstream_need = tuple(
        command_need[m]
        + min(gross["navoi_irrigation"][m], navoi_cap[m])
        + tpp_want[m]
        + new_want[m]
        + navoi_city[m]
        + industry[m]
        for m in range(N_STEPS)
    )
    gauge = RiverGauge()

    system.add_node(Source(id="inflow", inflow=TimeSeries(values=list(world.natural))))
    for node_id in ("samarkand_mi", "navoi_mi"):
        system.add_node(
            Demand(
                id=node_id,
                requirement=TimeSeries(values=list(municipal_requirement(world, node_id))),
                consumption_fraction=1.0 - MUNICIPAL_RETURN,
            )
        )
    system.add_node(
        Splitter(
            id="ravatkhoja_hw",
            split_policy=RavatkhojaPolicy(
                natural=world.natural,
                jizzakh_want=transfer_requirement("jizzakh"),
                kashkadarya_want=transfer_requirement("kashkadarya"),
                irrigation_gross=gross["samarkand_irrigation"],
                city_want=municipal_requirement(world, "samarkand_mi"),
                jizzakh_cap=_cap(JIZZAKH_CAP_M3S),
                kashkadarya_cap=_cap(KASHKADARYA_CAP_M3S),
                irrigation_cap=_cap(IRRIGATION_CAP_M3S["samarkand_irrigation"]),
                canal_supply=levers.canal_supply,
                transfer_share=levers.transfer_share,
                reserve_share=levers.reserve_share,
            ),
        )
    )
    for node_id in ("jizzakh", "kashkadarya"):
        system.add_node(Demand(id=node_id, requirement=TimeSeries(values=list(transfer_requirement(node_id)))))
        system.add_node(Sink(id=f"sink_{node_id}"))
    for index, (node_id, drain_id) in enumerate(DRAINS.items()):
        system.add_node(
            Demand(
                id=node_id,
                requirement=TimeSeries(values=[r * served / eta for r in irrigation_requirement(world, node_id)]),
                consumption_fraction=irrigation_cf,
                efficiency=served,
            )
        )
        system.add_node(
            Storage(
                id=drain_id,
                capacity=DRAIN_CAPACITY_MM3,
                initial_storage=drain_start[index],
                release_policy=LinearRecession(recession=world.drainage_recession),
                loss_rule=NoLoss(),
            )
        )
    system.add_node(
        Splitter(
            id="damkhoza",
            split_policy=DamkhozaPolicy(
                natural=world.natural,
                command_need=command_need,
                downstream_need=downstream_need,
                fill_cap=_cap(FILL_CAP_M3S),
                gauge=gauge,
                fill_share=levers.fill_share,
                reserve_share=levers.reserve_share,
            ),
        )
    )
    system.add_node(
        Storage(
            id="kattakurgan",
            capacity=world.capacity,
            initial_storage=world.start_storage,
            dead_storage=RESERVOIR_DEAD_MM3,
            release_policy=TopUpRelease(
                natural=world.natural,
                command_need=command_need,
                narpay_gross=narpay_gross(world),
                release_cap=_cap(RELEASE_CAP_M3S),
                gauge=gauge,
                release_share=levers.release_share,
                reserve_share=levers.reserve_share,
            ),
            loss_rule=TableEvaporation(depth_mm=tuple(e * world.evaporation_scale for e in EVAPORATION_MM)),
        )
    )
    system.add_node(
        Splitter(
            id="kattakurgan_hw",
            split_policy=CommandOfftakePolicy(
                natural=world.natural,
                gross=gross["kattakurgan_irrigation"],
                cap=command_cap,
                gauge=gauge,
                reserve_share=levers.reserve_share,
            ),
        )
    )
    system.add_node(
        Demand(
            id="navoi_industry",
            requirement=TimeSeries(values=list(industry)),
            consumption_fraction=INDUSTRY_CONSUMPTIVE,
        )
    )
    system.add_node(
        Splitter(
            id="karmana_intake",
            split_policy=IntakePolicy(
                natural=world.natural,
                want=tpp_want,
                want_new=new_want,
                tpp_return=1.0 - tpp_cf,
                new_return=1.0 - new_cf,
                tpp_priority=levers.tpp_priority,
                reserve_share=levers.reserve_share,
            ),
        )
    )
    system.add_node(Demand(id="navoi_tpp", requirement=TimeSeries(values=list(tpp_want)), consumption_fraction=tpp_cf))
    system.add_node(
        Demand(id="navoi_tpp_new", requirement=TimeSeries(values=list(new_want)), consumption_fraction=new_cf)
    )
    system.add_node(
        Splitter(
            id="karmana_hw",
            split_policy=OfftakePolicy(
                natural=world.natural,
                gross=gross["navoi_irrigation"],
                cap=_cap(IRRIGATION_CAP_M3S["navoi_irrigation"]),
                offtake_id="navoi_irrigation",
                river_id="eflow_navoi",
                reserve_share=levers.reserve_share,
            ),
        )
    )
    system.add_node(
        Demand(id="eflow_navoi", requirement=TimeSeries(values=list(eflow_target(world))), consumption_fraction=0.0)
    )
    system.add_node(Sink(id="bukhara"))
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


def _storage_path(node: Storage) -> list[float]:
    stored, lost, released = _monthly(node, WaterStored), _monthly(node, WaterLost), _monthly(node, WaterReleased)
    level = node.initial_storage
    path = []
    for s, loss, r in zip(stored, lost, released, strict=True):
        # Same operation order as Storage.update (store, lose, release) so the JavaScript twin matches exactly.
        level += s
        level -= loss
        level -= r
        path.append(level)
    return path


def node_balances(system: WaterSystem) -> dict[str, float]:
    """Largest monthly water-balance residual (Mm³) at every node, from the node's own events."""
    residuals: dict[str, float] = {}
    for node_id, node in system.nodes.items():
        received = _monthly(node, WaterReceived)
        if isinstance(node, Source):
            terms = [_monthly(node, WaterGenerated), [-v for v in _monthly(node, WaterOutput)]]
        elif isinstance(node, Splitter):
            terms = [received, [-v for v in _monthly(node, WaterDistributed)]]
        elif isinstance(node, Demand):
            terms = [received, *([-v for v in _monthly(node, e)] for e in (WaterOutput, WaterConsumed, WaterLost))]
        elif isinstance(node, Storage):
            path = _storage_path(node)
            previous = [node.initial_storage, *path[:-1]]
            change = [a - b for a, b in zip(path, previous, strict=True)]
            terms = [
                received,
                *([-v for v in _monthly(node, e)] for e in (WaterOutput, WaterLost)),
                [-c for c in change],
            ]
        else:
            continue
        residuals[node_id] = max(abs(sum(values)) for values in zip(*terms, strict=True))
    return residuals


def read_outcome(system: ZarafshanSystem) -> Outcome:
    """Turn a simulated system's events into monthly series and indicators."""
    world = system.world
    nodes = system.nodes
    eta, served, _ = irrigation_efficiencies(world)
    flows = _edge_flows(system)
    m: dict[str, list[float]] = {f"flow_{k}": v for k, v in flows.items()}
    m["inflow"] = list(world.natural)
    m["eflow_target"] = list(eflow_target(world))
    m["storage"] = _storage_path(nodes["kattakurgan"])
    m["fill"] = _monthly(nodes["kattakurgan"], WaterStored)
    m["fill_refused"] = _monthly(nodes["kattakurgan"], WaterSpilled)
    m["evaporation"] = _monthly(nodes["kattakurgan"], WaterLost)
    m["release"] = _monthly(nodes["kattakurgan"], WaterReleased)
    m["outflow"] = _monthly(nodes["bukhara"], WaterReceived)
    m["eflow_short"] = _monthly(nodes["eflow_navoi"], DeficitRecorded, "deficit")

    retained_total = [0.0] * N_STEPS
    conveyance = [0.0] * N_STEPS
    field_loss = [0.0] * N_STEPS
    drainage_in = [0.0] * N_STEPS
    consumed = [0.0] * N_STEPS
    transfers = [0.0] * N_STEPS
    for node_id, node in nodes.items():
        if not isinstance(node, Demand):
            continue
        received = _monthly(node, WaterReceived)
        output = _monthly(node, WaterOutput)
        retained = [r - o for r, o in zip(received, output, strict=True)]
        recorded = _monthly(node, DeficitRecorded, "deficit")
        m[f"received_{node_id}"] = received
        m[f"withdrawal_{node_id}"] = [
            min(a, r / node.efficiency) for a, r in zip(received, node.requirement.values, strict=True)
        ]
        m[f"output_{node_id}"] = output
        for t in range(N_STEPS):
            retained_total[t] += retained[t]
        if node_id in IRRIGATION_NODES:
            requirement = list(irrigation_requirement(world, node_id))
            deficit = [d * eta / served for d in recorded]
            m[f"requirement_{node_id}"] = requirement
            m[f"deficit_{node_id}"] = deficit
            m[f"delivered_{node_id}"] = [r - d for r, d in zip(requirement, deficit, strict=True)]
            m[f"conveyance_loss_{node_id}"] = [(1.0 - world.eta_c) * w for w in received]
            m[f"field_loss_{node_id}"] = [world.eta_c * (1.0 - world.eta_f) * w for w in received]
            m[f"consumed_{node_id}"] = retained
            for t in range(N_STEPS):
                conveyance[t] += m[f"conveyance_loss_{node_id}"][t]
                field_loss[t] += m[f"field_loss_{node_id}"][t]
                drainage_in[t] += output[t]
                consumed[t] += retained[t]
            continue
        m[f"requirement_{node_id}"] = list(node.requirement.values)
        m[f"deficit_{node_id}"] = recorded
        m[f"delivered_{node_id}"] = [r - d for r, d in zip(node.requirement.values, recorded, strict=True)]
        if node_id in ("jizzakh", "kashkadarya"):
            for t in range(N_STEPS):
                transfers[t] += retained[t]
        elif node_id != "eflow_navoi":
            m[f"consumed_{node_id}"] = retained
            for t in range(N_STEPS):
                consumed[t] += retained[t]
    drainage_out = [0.0] * N_STEPS
    drain_start = 0.0
    drain_end = 0.0
    for drain_id in DRAINS.values():
        path = _storage_path(nodes[drain_id])
        m[f"storage_{drain_id}"] = path
        released = _monthly(nodes[drain_id], WaterReleased)
        for t in range(N_STEPS):
            drainage_out[t] += released[t]
        drain_start += nodes[drain_id].initial_storage
        drain_end += path[-1]
    m["conveyance_loss"] = conveyance
    m["field_loss"] = field_loss
    m["drainage_in"] = drainage_in
    m["drainage_return"] = drainage_out
    m["consumed"] = consumed
    m["transfers"] = transfers
    tpp_want = _cap(TPP_WITHDRAWAL_M3S)
    tpp_min = _cap(TPP_MIN_INTAKE_M3S)
    new_want = _cap(world.tpp_new_withdrawal_m3s)
    m["tpp_output_fraction"] = [min(1.0, w / want) for w, want in zip(m["withdrawal_navoi_tpp"], tpp_want, strict=True)]
    m["tpp_new_output_fraction"] = [
        min(1.0, w / want) if want > 0 else 1.0 for w, want in zip(m["withdrawal_navoi_tpp_new"], new_want, strict=True)
    ]
    m["energy_not_generated_gwh"] = [
        (TPP_RIVER_COOLED_MW * (1.0 - phi) + world.tpp_new_mw * (1.0 - phi_new)) * TPP_CAPACITY_FACTOR * 24 * d / 1000.0
        for d, phi, phi_new in zip(DAYS, m["tpp_output_fraction"], m["tpp_new_output_fraction"], strict=True)
    ]
    m["outflow_m3s"] = [flow(v, d) for v, d in zip(m["outflow"], DAYS, strict=True)]

    initial = nodes["kattakurgan"].initial_storage
    ind: dict[str, float] = {
        "inflow": sum(world.natural),
        "storage_initial": initial,
        "end_storage": m["storage"][-1],
        "storage_change": m["storage"][-1] - initial,
        "storage_min": min(m["storage"]),
        "evaporation": sum(m["evaporation"]),
        "fill": sum(m["fill"]),
        "fill_refused": sum(m["fill_refused"]),
        "release": sum(m["release"]),
        "spill": 0.0,
        "conveyance_loss": sum(conveyance),
        "field_loss": sum(field_loss),
        "drainage_in": sum(drainage_in),
        "drainage_return": sum(drainage_out),
        "drainage_store_start": drain_start,
        "drainage_store_end": drain_end,
        "consumed": sum(consumed),
        "tpp_consumed": sum(m["consumed_navoi_tpp"]) + sum(m["consumed_navoi_tpp_new"]),
        "transfers_delivered": sum(transfers),
        "outflow": sum(m["outflow"]),
        "outflow_min_m3s": min(m["outflow_m3s"]),
        "eflow_short": sum(m["eflow_short"]),
        "energy_not_generated_gwh": sum(m["energy_not_generated_gwh"]),
    }
    ind["balance_error"] = (
        ind["inflow"]
        + initial
        + drain_start
        - ind["end_storage"]
        - drain_end
        - ind["evaporation"]
        - sum(retained_total)
        - ind["outflow"]
    )

    def supply(node_ids: Iterable[str]) -> float:
        req = sum(sum(m[f"requirement_{n}"]) for n in node_ids)
        deficit = sum(sum(m[f"deficit_{n}"]) for n in node_ids)
        return 100.0 * (req - deficit) / req if req > 0 else 100.0

    ind["irrigation_supply"] = supply(IRRIGATION_NODES)
    ind["irrigation_upstream"] = supply(("samarkand_irrigation",))
    ind["irrigation_tail"] = supply(("kattakurgan_irrigation", "navoi_irrigation"))
    ind["irrigation_deficit"] = sum(sum(m[f"deficit_{n}"]) for n in IRRIGATION_NODES)
    ind["transfer_delivery"] = supply(("jizzakh", "kashkadarya"))
    ind["transfer_deficit"] = sum(m["deficit_jizzakh"]) + sum(m["deficit_kashkadarya"])
    ind["tpp_months"] = float(
        sum(1 for w, lo in zip(m["withdrawal_navoi_tpp"], tpp_min, strict=True) if w >= lo - 1e-9)
    )
    ind["tpp_deficit"] = sum(m["deficit_navoi_tpp"])
    ind["eflow_months"] = float(sum(1 for s in m["eflow_short"] if s <= 1e-9))
    ind["samarkand_mi_shortfall"] = sum(m["deficit_samarkand_mi"])
    ind["navoi_mi_shortfall"] = sum(m["deficit_navoi_mi"]) + sum(m["deficit_navoi_industry"])
    ind["municipal_shortfall"] = ind["samarkand_mi_shortfall"] + ind["navoi_mi_shortfall"]
    ind["equity"] = ind["irrigation_upstream"] - ind["irrigation_tail"]
    return Outcome(monthly={k: tuple(v) for k, v in m.items()}, indicators=ind)


def simulate(settings: Settings, cards: Iterable[str], year: str, levers: Levers) -> ZarafshanSystem:
    """Build and run the system for one hydrological year; returns the simulated TaqSim system."""
    system = build_system(resolve(settings, cards, year), levers)
    system.simulate(N_STEPS)
    return system


def evaluate(settings: Settings, cards: Iterable[str], year: str, levers: Levers) -> Outcome:
    """Simulate one hydrological year with TaqSim and summarise the result."""
    return read_outcome(simulate(settings, cards, year, levers))


# --- Objectives ------------------------------------------------------------------------------------------
def _irrigation_deficit(node_ids: Iterable[str] = IRRIGATION_NODES) -> Objective:
    ids = tuple(node_ids)

    def evaluate_total(system: WaterSystem) -> float:
        eta, served, _ = irrigation_efficiencies(system.world)
        return sum(system.nodes[n].trace(DeficitRecorded, field="deficit").sum() for n in ids) * eta / served

    return Objective(name="irrigation_deficit", direction="minimize", evaluate=evaluate_total)


def _transfer_deficit() -> Objective:
    jizzakh, kashkadarya = minimize_objectives.deficit("jizzakh"), minimize_objectives.deficit("kashkadarya")
    return Objective(
        name="transfer_deficit",
        direction="minimize",
        evaluate=lambda system: jizzakh.evaluate(system) + kashkadarya.evaluate(system),
    )


def _end_storage() -> Objective:
    return Objective(
        name="end_storage",
        direction="maximize",
        evaluate=lambda system: _storage_path(system.nodes["kattakurgan"])[-1],
    )


if "irrigation_deficit" not in minimize_objectives.list_available():
    minimize_objectives.register("irrigation_deficit", _irrigation_deficit)

OBJECTIVES = ("irrigation_deficit", "transfer_deficit", "navoi_tpp.deficit", "eflow_navoi.deficit", "end_storage")
# The five explorer axes, all oriented higher-is-better.
AXES = ("irrigation_supply", "transfer_delivery", "tpp_months", "eflow_months", "end_storage")


def objectives() -> list[Objective]:
    return [
        minimize_objectives.irrigation_deficit(),
        _transfer_deficit(),
        minimize_objectives.deficit("navoi_tpp"),
        minimize_objectives.deficit("eflow_navoi"),
        _end_storage(),
    ]


@dataclass(frozen=True)
class FrontMember:
    levers: Levers
    objectives: dict[str, float]
    indicators: dict[str, dict[str, float]]  # per year


def optimise(
    settings: Settings,
    cards: Iterable[str],
    year: str = "dry",
    pop_size: int = 100,
    generations: int = 100,
    seed: int = 42,
) -> list[FrontMember]:
    """NSGA-II over the six levers on one inflow year; each front member is then re-run on all three years."""
    active = tuple(sorted(set(cards)))
    result = taqsim_optimize(
        system=build_system(resolve(settings, active, year), Levers()),
        objectives=objectives(),
        timesteps=N_STEPS,
        pop_size=pop_size,
        generations=generations,
        seed=seed,
    )
    members = []
    for solution in result:
        levers = levers_from_parameters(solution.parameters)
        members.append(
            FrontMember(
                levers=levers,
                objectives={name: float(solution.scores[name]) for name in OBJECTIVES},
                indicators={y: evaluate(settings, active, y, levers).indicators for y in YEARS},
            )
        )
    logger.info("front cards=%s year=%s: %d members", active or "none", year, len(members))
    return members


# --- Dense search and trade-off envelope -----------------------------------------------------------------
def display_members(members: list[FrontMember], year: str) -> list[FrontMember]:
    """The optimiser's plans that no other of its plans beats on the five display axes of the optimised year.

    NSGA-II compares plans on shortfall volumes; the page compares them on the display axes, two of which count
    months. A plan can be unbeaten on volumes and beaten on month counts, so the set is reduced before display.
    """
    rows = [tuple(float(member.indicators[year][a]) for a in AXES) for member in members]
    best = set(non_dominated(rows))
    seen: set[tuple[float, ...]] = set()
    out = []
    for member, row in zip(members, rows, strict=True):
        if row in best and row not in seen:
            seen.add(row)
            out.append(member)
    return out


def latin_hypercube(n: int, seed: int) -> list[Levers]:
    """`n` lever sets covering the lever ranges evenly (Latin hypercube; the TPP priority is 0 or 1)."""
    rng = random.Random(seed)
    columns = {}
    for name, (lo, hi) in LEVER_BOUNDS.items():
        strata = list(range(n))
        rng.shuffle(strata)
        columns[name] = [lo + (s + rng.random()) / n * (hi - lo) for s in strata]
    plans = []
    for i in range(n):
        values = {name: columns[name][i] for name in LEVER_BOUNDS}
        values["tpp_priority"] = 1.0 if values["tpp_priority"] >= 0.5 else 0.0
        plans.append(Levers(**values))
    return plans


def dense_search(
    settings: Settings, cards: Iterable[str], year: str, n: int = 20_000, seed: int = 7
) -> list[tuple[Levers, dict[str, float]]]:
    """Evaluate `n` Latin-hypercube plans for one year; returns (levers, indicators) pairs."""
    active = tuple(sorted(set(cards)))
    return [(levers, evaluate(settings, active, year, levers).indicators) for levers in latin_hypercube(n, seed)]


def dominates(a: Iterable[float], b: Iterable[float]) -> bool:
    """True when `a` is at least as good as `b` on every axis and better on one (higher is better)."""
    strictly = False
    for x, y in zip(a, b, strict=True):
        if x < y - 1e-9:
            return False
        if x > y + 1e-9:
            strictly = True
    return strictly


# Cells of the trade-off table: least transfer supply (%), least cooled months, least e-flow months.
ENVELOPE_CELLS: tuple[tuple[float, int, int], ...] = tuple(
    (transfers, tpp, eflow) for transfers, tpp in ((0.0, 0), (90.0, 10), (90.0, 12)) for eflow in (0, 8, 12)
)


def in_cell(indicators: dict[str, float], cell: tuple[float, int, int]) -> bool:
    transfers, tpp, eflow = cell
    return (
        indicators["transfer_delivery"] >= transfers - 1e-9
        and indicators["tpp_months"] >= tpp
        and indicators["eflow_months"] >= eflow
    )


def tradeoff_envelope(plans: Iterable[dict[str, float]]) -> dict:
    """Best irrigation supply found in a pool of plans under each set of conditions; None where no plan qualifies.

    "Protected" plans supply at least 90 % of the transfers and cool the power plant in at least 10 months.
    """
    everyone = list(plans)
    protected = [p for p in everyone if in_cell(p, (90.0, 10, 0))]

    def best(cell: tuple[float, int, int]) -> float | None:
        values = [p["irrigation_supply"] for p in everyone if in_cell(p, cell)]
        return max(values) if values else None

    at_8, at_12, any_eflow = best((90.0, 10, 8)), best((90.0, 10, 12)), best((90.0, 10, 0))
    months = [p["eflow_months"] for p in protected if p["irrigation_supply"] >= 85.0]
    return {
        "plans": len(everyone),
        "plans_with_transfers_ge_90_and_tpp_ge_10": len(protected),
        "best_irrigation_any_eflow": any_eflow,
        "best_irrigation_at_eflow_ge_8": at_8,
        "best_irrigation_at_eflow_12": at_12,
        "irrigation_points_lost_from_8_to_12_eflow_months": at_8 - at_12
        if at_8 is not None and at_12 is not None
        else None,
        "irrigation_points_lost_for_12_eflow_months": any_eflow - at_12
        if any_eflow is not None and at_12 is not None
        else None,
        "best_eflow_months_at_irrigation_ge_85": max(months) if months else None,
        "table": [
            {"transfers_min": cell[0], "tpp_min": cell[1], "eflow_min": cell[2], "best_irrigation": best(cell)}
            for cell in ENVELOPE_CELLS
        ],
    }


def refine_best_irrigation(
    settings: Settings,
    cards: Iterable[str],
    year: str,
    start: Levers,
    cell: tuple[float, int, int],
    steps: tuple[float, ...] = (0.1, 0.05, 0.02, 0.01, 0.005),
) -> tuple[Levers, dict[str, float]]:
    """Pattern search from `start` for more irrigation supply without leaving the cell's conditions.

    A random search rarely lands on the edge of a condition; this walks the best plans found up to that edge, so
    that the quoted "best found" is not beaten by the next random search.
    """
    active = tuple(sorted(set(cards)))
    best_levers, best = start, evaluate(settings, active, year, start).indicators
    for step in steps:
        improved = True
        while improved:
            improved = False
            candidates = [replace(best_levers, tpp_priority=1.0 - best_levers.tpp_priority)]
            for name, (lo, hi) in LEVER_BOUNDS.items():
                if name == "tpp_priority":
                    continue
                for direction in (-1.0, 1.0):
                    value = min(max(getattr(best_levers, name) + direction * step * (hi - lo), lo), hi)
                    candidates.append(replace(best_levers, **{name: value}))
            for levers in candidates:
                indicators = evaluate(settings, active, year, levers).indicators
                if in_cell(indicators, cell) and indicators["irrigation_supply"] > best["irrigation_supply"] + 1e-6:
                    best_levers, best, improved = levers, indicators, True
    return best_levers, best


def refined_plans(
    settings: Settings, cards: Iterable[str], year: str, pool: list[tuple[Levers, dict[str, float]]], starts: int = 3
) -> list[tuple[Levers, dict[str, float]]]:
    """For every cell of the trade-off table, refine the `starts` best plans of the pool."""
    out = []
    for cell in ENVELOPE_CELLS:
        ranked = sorted((p for p in pool if in_cell(p[1], cell)), key=lambda p: -p[1]["irrigation_supply"])
        out.extend(refine_best_irrigation(settings, cards, year, levers, cell) for levers, _ in ranked[:starts])
    return out


def non_dominated(rows: Iterable[tuple[float, ...]]) -> list[tuple[float, ...]]:
    """The distinct rows that no other row beats (higher is better on every axis)."""
    points = np.array(sorted(set(rows)), dtype=float)
    keep = []
    for i, row in enumerate(points):
        at_least = (points >= row - 1e-9).all(axis=1)
        better = (points > row + 1e-9).any(axis=1)
        if not (at_least & better).any():
            keep.append(tuple(float(v) for v in points[i]))
    return keep


def hypervolume(front: Iterable[tuple[float, ...]], upper: tuple[float, ...], n: int = 20_000, seed: int = 1) -> float:
    """Share of the box between zero and `upper` that `front` covers (seeded Monte Carlo; higher is better)."""
    rng = random.Random(seed)
    points = np.array([[rng.random() * u for u in upper] for _ in range(n)])
    covered = np.zeros(n, dtype=bool)
    for member in front:
        covered |= (points <= np.asarray(member, dtype=float)).all(axis=1)
    return float(covered.mean())


def front_coverage(
    front: list[tuple[float, ...]], dense: list[tuple[float, ...]], upper: tuple[float, ...]
) -> dict[str, float]:
    """How much of what a dense random search finds an optimiser front covers, on the five display axes."""
    dense_best = non_dominated(dense)
    union = non_dominated([*front, *dense_best])
    hv_front, hv_union = hypervolume(front, upper), hypervolume(union, upper)
    front_array, dense_array = np.array(front, dtype=float), np.array(dense, dtype=float)
    covered = sum(bool((front_array >= row - 1e-9).all(axis=1).any()) for row in dense_array)
    return {
        "front_members": len(front),
        "dense_plans": len(dense),
        "dense_non_dominated": len(dense_best),
        "hypervolume_front": hv_front,
        "hypervolume_dense": hypervolume(dense_best, upper),
        "hypervolume_union": hv_union,
        "front_share_of_union_hypervolume": hv_front / hv_union if hv_union else 0.0,
        "front_members_beaten_by_dense": sum(any(dominates(d, f) for d in dense_best) for f in front),
        "dense_share_matched_or_beaten_by_front": covered / len(dense) if dense else 0.0,
    }


# --- Round-1 role targets --------------------------------------------------------------------------------
# Two indicators per role with a target for the dry year without cards. The values were chosen from the dense
# search (20 000 plans, seed 7) so that every role can reach its own pair and no plan reaches all five pairs;
# `role_target_check` re-counts this for any pool and the export records the counts.
ROLE_TARGETS: dict[str, tuple[tuple[str, str, float], ...]] = {
    "R1": (("irrigation_upstream", ">=", 95.0), ("samarkand_mi_shortfall", "<=", 0.0)),
    "R2": (("irrigation_tail", ">=", 80.0), ("end_storage", ">=", 170.0)),
    "R3": (("tpp_months", ">=", 12.0), ("navoi_mi_shortfall", "<=", 0.0)),
    "R4": (("transfer_delivery", ">=", 95.0), ("outflow", ">=", 1000.0)),
    "R5": (("eflow_months", ">=", 12.0), ("outflow_min_m3s", ">=", 10.0)),
}


def meets_targets(indicators: dict[str, float], targets: Iterable[tuple[str, str, float]]) -> bool:
    return all(
        indicators[key] >= value - 1e-9 if op == ">=" else indicators[key] <= value + 1e-9 for key, op, value in targets
    )


def role_target_check(plans: Iterable[dict[str, float]]) -> dict:
    """Number of plans in a pool that reach each role's targets, and that reach all of them together."""
    pool = list(plans)
    return {
        "plans": len(pool),
        "reachable": {role: sum(meets_targets(p, t) for p in pool) for role, t in ROLE_TARGETS.items()},
        "all_roles_together": sum(all(meets_targets(p, t) for t in ROLE_TARGETS.values()) for p in pool),
    }


# --- Comparison with the record --------------------------------------------------------------------------
# Tolerance declared before the calibration (IMPLEMENTATION_NOTES.md, "Audit round: declarations").
CALIBRATION_TOLERANCE = {"mae_m3s": 10.0, "volume_pct": 25.0}
# Kattakurgan ten-day storage record 2000-2022, medians converted to the model's volume frame with
# official = 123.2 + 1.025 x model (read: workshop/zarafshan_game/research/kattakurgan_storage.md:63,102,113,115,128).
OFFICIAL_PER_MODEL_VOLUME = 1.025
OBSERVED_STORAGE_CYCLE: dict[str, float | str] = {
    "winter_rise": 450.0 / OFFICIAL_PER_MODEL_VOLUME,
    "fall_to_sep": 307.0 / OFFICIAL_PER_MODEL_VOLUME,
    "dec_feb_rise": 399.0 / OFFICIAL_PER_MODEL_VOLUME,
    "month_max": "Mar",
    "month_min": "Nov",
}
WINTER = (2, 3, 4)  # December-February
SUMMER = (8, 9, 10)  # June-August
COOL_SEASON = tuple(range(7))  # October-April, the months the calibration tolerance refers to


def storage_cycle(outcome: Outcome) -> dict[str, float | str]:
    """Winter rise (autumn low to the end of March), peak month, lowest month and the fall from the peak to 30 Sep."""
    path = list(outcome.monthly["storage"])
    peak = max(path)
    autumn_low = min(outcome.indicators["storage_initial"], path[0], path[1])
    return {
        "winter_rise": path[MONTHS.index("Mar")] - autumn_low,
        "fall_to_sep": peak - path[-1],
        "month_max": MONTHS[path.index(peak)],
        "month_min": MONTHS[path.index(min(path))],
    }


def months_meeting_target(flows_m3s: Iterable[float], year: str, settings: Settings) -> int:
    """Months in which a flow series at Navoi reaches the e-flow target of the year without cards."""
    target = eflow_target(resolve(settings, (), year))
    return sum(volume(q, d) >= v - 1e-9 for q, d, v in zip(flows_m3s, DAYS, target, strict=True))


def navoi_comparison(settings: Settings) -> dict:
    """Modelled flow at Navoi against the gauge, for the comparison plan and the starting plan, per year."""
    comparison = {}
    for year in YEARS:
        gauge = NAVOI_GAUGE_M3S[year]
        row: dict[str, object] = {
            "gauge_m3s": gauge,
            "gauge_eflow_months": months_meeting_target(gauge, year, settings),
        }
        for name, levers in (("model", HISTORICAL_PLAN), ("start_plan", Levers())):
            modelled = evaluate(settings, (), year, levers).monthly["outflow_m3s"]
            cool_model = sum(volume(modelled[t], DAYS[t]) for t in COOL_SEASON)
            cool_gauge = sum(volume(gauge[t], DAYS[t]) for t in COOL_SEASON)
            row[f"{name}_m3s"] = tuple(modelled)
            row[f"{name}_eflow_months"] = months_meeting_target(modelled, year, settings)
            row[f"{name}_mae_oct_apr"] = sum(abs(modelled[t] - gauge[t]) for t in COOL_SEASON) / len(COOL_SEASON)
            row[f"{name}_volume_error_pct_oct_apr"] = 100.0 * (cool_model - cool_gauge) / cool_gauge
        comparison[year] = row
    past = evaluate(settings, (), "median", HISTORICAL_PLAN)
    gauge = [volume(q, d) for q, d in zip(NAVOI_GAUGE_M3S["median"], DAYS, strict=True)]
    inflow, outflow = past.monthly["inflow"], past.monthly["outflow"]
    # December-February balance of the river and the reservoir: what leaves or is stored, less what Ravatkhoja delivers,
    # must come from gains along the river. Use, transfers and evaporation are the model's; the rest is the record.
    winter_use = sum(past.monthly["consumed"][t] for t in WINTER)
    winter_transfers = sum(past.monthly["transfers"][t] for t in WINTER)
    winter_evaporation = sum(past.monthly["evaporation"][t] for t in WINTER)
    winter_needed = (
        sum(gauge[t] - inflow[t] for t in WINTER)
        + float(OBSERVED_STORAGE_CYCLE["dec_feb_rise"])
        + winter_use
        + winter_transfers
        + winter_evaporation
    )
    winter_drainage = sum(past.monthly["drainage_return"][t] for t in WINTER)
    return {
        "plan": asdict(HISTORICAL_PLAN),
        "tolerance": CALIBRATION_TOLERANCE,
        "tolerance_met": comparison["median"]["model_mae_oct_apr"] <= CALIBRATION_TOLERANCE["mae_m3s"]
        and abs(comparison["median"]["model_volume_error_pct_oct_apr"]) <= CALIBRATION_TOLERANCE["volume_pct"],
        "comparison": comparison,
        "diagnosis": {
            "summer_observed_loss_mm3": sum(inflow[t] - gauge[t] for t in SUMMER),
            "summer_model_loss_mm3": sum(inflow[t] - outflow[t] for t in SUMMER),
            "winter_inflow_mm3": sum(inflow[t] for t in WINTER),
            "winter_gauge_mm3": sum(gauge[t] for t in WINTER),
            "winter_storage_rise_observed_mm3": float(OBSERVED_STORAGE_CYCLE["dec_feb_rise"]),
            "winter_use_mm3": winter_use,
            "winter_transfers_mm3": winter_transfers,
            "winter_evaporation_mm3": winter_evaporation,
            "winter_gain_needed_mm3": winter_needed,
            "winter_drainage_mm3": winter_drainage,
            "winter_gap_mm3": winter_needed - winter_drainage,
        },
    }


def storage_comparison(settings: Settings) -> dict:
    """Modelled Kattakurgan cycle in the mean year against the medians of the storage record."""
    return {
        "observed": OBSERVED_STORAGE_CYCLE,
        "historical": storage_cycle(evaluate(settings, (), "median", HISTORICAL_PLAN)),
        "start_plan": storage_cycle(evaluate(settings, (), "median", Levers())),
        "start_plan_dry": storage_cycle(evaluate(settings, (), "dry", Levers())),
    }


# Lever(s) each role holds in the table rounds (the page's role cards use the same assignment).
ROLE_LEVERS: dict[str, tuple[str, ...]] = {
    "R1": ("canal_supply",),
    "R2": ("fill_share", "release_share"),
    "R3": ("tpp_priority",),
    "R4": ("transfer_share",),
    "R5": ("reserve_share",),
}
EFFECT_KEYS = ("irrigation_supply", "tpp_months", "eflow_months", "end_storage", "outflow", "drainage_return")


def drainage_store_change(indicators: dict[str, float]) -> float:
    return indicators["drainage_store_end"] - indicators["drainage_store_start"]


def own_lever_reach(settings: Settings, steps: int = 21) -> dict[str, dict[str, int]]:
    """Dry year, no card: how many settings of a role's own lever(s) alone reach its Round-1 targets."""
    out = {}
    for role, names in ROLE_LEVERS.items():
        grids = [
            (0.0, 1.0) if name == "tpp_priority" else tuple(lo + i * (hi - lo) / (steps - 1) for i in range(steps))
            for name in names
            for lo, hi in (LEVER_BOUNDS[name],)
        ]
        combos = list(itertools.product(*grids))
        reached = sum(
            meets_targets(
                evaluate(settings, (), "dry", replace(Levers(), **dict(zip(names, c, strict=True)))).indicators,
                ROLE_TARGETS[role],
            )
            for c in combos
        )
        out[role] = {"reached": reached, "tried": len(combos)}
    return out


def plant_priority_effect(settings: Settings, dense: list[tuple[Levers, dict[str, float]]]) -> dict:
    """What lever L5 does: under the starting plan in each year, and on average over a pool of plans."""

    def pair(levers: Levers, year: str) -> dict[str, float]:
        indicators = evaluate(settings, (), year, levers).indicators
        return {"tpp_months": indicators["tpp_months"], "eflow_months": indicators["eflow_months"]}

    def mean_eflow(priority: float) -> float | None:
        values = [ind["eflow_months"] for levers, ind in dense if levers.tpp_priority == priority]
        return sum(values) / len(values) if values else None

    return {
        "start_plan": {
            year: {
                "plant_first": pair(Levers(tpp_priority=1.0), year),
                "after_reserve": pair(Levers(tpp_priority=0.0), year),
            }
            for year in YEARS
        },
        "dense_mean_eflow_months": {"plant_first": mean_eflow(1.0), "after_reserve": mean_eflow(0.0)},
    }


def card_effects(settings: Settings) -> dict:
    """Change that C3, C4, C6 and C8 make to the starting plan (and C4, C8 with a fill share of 0.8), per year."""

    def delta(card: str, year: str, levers: Levers, s: Settings = settings) -> dict[str, float]:
        base = evaluate(s, (), year, levers).indicators
        with_card = evaluate(s, (card,), year, levers).indicators
        return {k: with_card[k] - base[k] for k in EFFECT_KEYS}

    high_fill = replace(Levers(), fill_share=0.8)
    out: dict[str, dict] = {card: {y: delta(card, y, Levers()) for y in YEARS} for card in ("C3", "C4", "C6", "C8")}
    out["C4_fill_share_0.8"] = {y: delta("C4", y, high_fill) for y in YEARS}
    out["C8_fill_share_0.8"] = {y: delta("C8", y, high_fill) for y in YEARS}
    out["C6_once_through"] = {y: delta("C6", y, Levers(), replace(settings, expansion_once_through=1.0)) for y in YEARS}
    return out


def drainage_store_summary(settings: Settings, dense: list[tuple[Levers, dict[str, float]]]) -> dict:
    """Start content of the drainage stores and how much plans change it within the year (dry-year pool)."""
    changes = sorted(drainage_store_change(ind) for _, ind in dense)

    def at(share: float) -> float | None:
        return changes[round(share * (len(changes) - 1))] if changes else None

    start = {y: evaluate(settings, (), y, Levers()).indicators for y in YEARS}
    return {
        "start_mm3": {y: start[y]["drainage_store_start"] for y in YEARS},
        "start_plan_change_mm3": {y: drainage_store_change(start[y]) for y in YEARS},
        "dry_pool_change_mm3": {"min": at(0.0), "p05": at(0.05), "median": at(0.5), "p95": at(0.95), "max": at(1.0)},
        "dry_reserve_0.4_change_mm3": drainage_store_change(
            evaluate(settings, (), "dry", replace(Levers(), reserve_share=0.4)).indicators
        ),
        "dry_start_with_card_mm3": {
            card: evaluate(settings, (card,), "dry", Levers()).indicators["drainage_store_start"]
            for card in ("C3", "C5")
        },
    }


def _axis_rows(rows: Iterable[dict[str, float]]) -> list[tuple[float, ...]]:
    return [tuple(float(row[a]) for a in AXES) for row in rows]


def analyse(
    fronts: dict[str, list[tuple[Levers, dict[str, float]]]], dense_n: int = 20_000, dense_seed: int = 7
) -> dict:
    """Envelope, front coverage, role targets and the comparison with the record, for the page and key numbers.

    `fronts` holds, per front name, the displayed members as (levers, dry-year indicators).
    """
    settings = Settings()
    pools = {"dry": ((), "F1"), "dry_c5": (("C5",), "F2")}
    envelope, coverage = {}, {}
    role_targets: dict = {}
    plant_priority: dict = {}
    drainage_stores: dict = {}
    for name, (cards, front_name) in pools.items():
        dense = dense_search(settings, cards, "dry", n=dense_n, seed=dense_seed)
        members = fronts.get(front_name, [])
        start = (Levers(), evaluate(settings, cards, "dry", Levers()).indicators)
        refined = refined_plans(settings, cards, "dry", [*dense, *members, start])
        dense_rows, member_rows = [ind for _, ind in dense], [ind for _, ind in members]
        envelope[name] = tradeoff_envelope([*dense_rows, *member_rows, start[1], *(ind for _, ind in refined)])
        envelope[name]["refined_plans"] = len(refined)
        if members:
            upper = (100.0, 100.0, 12.0, 12.0, resolve(settings, cards, "dry").capacity)
            coverage[front_name] = front_coverage(_axis_rows(member_rows), _axis_rows(dense_rows), upper)
        if name == "dry":
            role_targets = {
                "targets": {
                    role: [{"key": key, "op": op, "value": value} for key, op, value in targets]
                    for role, targets in ROLE_TARGETS.items()
                },
                "check": role_target_check([*dense_rows, *member_rows, *(ind for _, ind in refined)]),
                "own_levers": own_lever_reach(settings),
            }
            plant_priority = plant_priority_effect(settings, dense)
            drainage_stores = drainage_store_summary(settings, dense)
        logger.info("analysis %s: %d dense, %d front, %d refined plans", name, len(dense), len(members), len(refined))
    return {
        "dense": {"n": dense_n, "seed": dense_seed, "sampling": "Latin hypercube over the six levers"},
        "envelope": envelope,
        "coverage": coverage,
        "role_targets": role_targets,
        "plant_priority": plant_priority,
        "cards": card_effects(settings),
        "drainage_stores": drainage_stores,
        "start_plan": {y: evaluate(settings, (), y, Levers()).indicators for y in YEARS},
        "navoi": navoi_comparison(settings),
        "storage_cycle": storage_comparison(settings),
    }


def refresh_analysis(path: Path, dense_n: int = 20_000) -> None:
    """Recompute constants, reference cases and the `analysis` block of an exported file, keeping its fronts."""
    data = json.loads(Path(path).read_text())
    data["reference_cases"] = build_reference_cases(len(data["reference_cases"]), data["meta"]["optimiser"]["seed"])
    data["constants"] = json.loads(json.dumps(game_constants()))
    fronts = {
        name: [(Levers(**member["levers"]), member["indicators"]["dry"]) for member in front["members"]]
        for name, front in data["fronts"].items()
    }
    data["analysis"] = analyse(fronts, dense_n=dense_n)
    Path(path).write_text(json.dumps(data, separators=(",", ":")))
    logger.info("refreshed the analysis in %s", path)


FRONTS: dict[str, tuple[tuple[str, ...], str]] = {
    "F0": ((), "median"),
    "F1": ((), "dry"),
    "F2": (("C5",), "dry"),
    "F3": (("C1", "C6"), "dry"),
    "F4": (("C2", "C7"), "dry"),
    "F5": (("C3",), "dry"),
    "F6": (("C4", "C5"), "dry"),
    "F7": (("C7",), "dry"),
}

CANONICAL_CASES: tuple[tuple[Settings, tuple[str, ...], str, Levers], ...] = (
    (Settings(), (), "dry", Levers()),
    (Settings(), (), "median", Levers()),
    (Settings(), (), "wet", Levers()),
    (Settings(), ("C5",), "dry", Levers()),
    (Settings(), ("C3",), "dry", Levers()),
    (Settings(), ("C4", "C5"), "wet", Levers(fill_share=0.8)),
    (Settings(), (), "dry", Levers(reserve_share=0.0, fill_share=0.8)),
    (Settings(), ("C1", "C6"), "dry", Levers(tpp_priority=0.0)),
    (Settings(expansion_once_through=1.0), ("C6",), "dry", Levers(tpp_priority=0.0, reserve_share=0.3)),
    (Settings(), (), "median", HISTORICAL_PLAN),
)


def _random_case(rng: random.Random) -> tuple[Settings, tuple[str, ...], str, Levers]:
    settings = Settings(**{name: rng.uniform(lo, hi) for name, (lo, hi) in SETTING_BOUNDS.items()})
    cards = tuple(c for c in CARDS if rng.random() < 0.3)
    levers = Levers(**{name: rng.uniform(lo, hi) for name, (lo, hi) in LEVER_BOUNDS.items()})
    return settings, cards, rng.choice(YEARS), levers


# Indicators kept for every front member and year in the exported file (the page shows these; the rest is
# recomputed by the browser model on demand).
MEMBER_INDICATORS = (
    "irrigation_supply",
    "irrigation_upstream",
    "irrigation_tail",
    "transfer_delivery",
    "tpp_months",
    "eflow_months",
    "eflow_short",
    "end_storage",
    "storage_change",
    "outflow",
    "outflow_min_m3s",
    "samarkand_mi_shortfall",
    "navoi_mi_shortfall",
    "energy_not_generated_gwh",
    "balance_error",
)


def game_constants() -> dict:
    """Static inputs the browser model needs, in hydrological-year order."""
    return {
        "months": MONTHS,
        "days_in_month": DAYS,
        "fill_months": sorted(FILL_MONTHS),
        "flood_fill_months": sorted(FLOOD_FILL_MONTHS),
        "release_months": sorted(RELEASE_MONTHS),
        "years": {
            y: {"label": YEAR_LABELS[y], "inflow_m3s": INFLOW_M3S[y], "navoi_gauge_m3s": NAVOI_GAUGE_M3S[y]}
            for y in YEARS
        },
        "transfers_m3s": {"jizzakh": JIZZAKH_M3S, "kashkadarya": KASHKADARYA_M3S},
        "transfer_caps_m3s": {"jizzakh": JIZZAKH_CAP_M3S, "kashkadarya": KASHKADARYA_CAP_M3S},
        "irrigation_requirement_mm3": IRRIGATION_REQ_MM3,
        "narpay_requirement_mm3": NARPAY_REQ_MM3,
        "irrigation_caps_m3s": IRRIGATION_CAP_M3S,
        "drains": DRAINS,
        "drainage_recession": DRAINAGE_RECESSION,
        "evaporation_mm": EVAPORATION_MM,
        "va_volume_mm3": VA_VOLUME_MM3,
        "va_area_km2": VA_AREA_KM2,
        "reservoir": {
            "capacity": RESERVOIR_CAPACITY_MM3,
            "dead": RESERVOIR_DEAD_MM3,
            "initial": START_STORAGE_MM3,
            "initial_range": START_STORAGE_RANGE_MM3,
            "fill_cap_m3s": FILL_CAP_M3S,
            "release_cap_m3s": RELEASE_CAP_M3S,
        },
        "population": POPULATION,
        "municipal_return": MUNICIPAL_RETURN,
        "industry_consumptive": INDUSTRY_CONSUMPTIVE,
        "tpp": {
            "withdrawal_m3s": TPP_WITHDRAWAL_M3S,
            "min_intake_m3s": TPP_MIN_INTAKE_M3S,
            "capacity_mw": TPP_CAPACITY_MW,
            "river_cooled_mw": TPP_RIVER_COOLED_MW,
            "new_units_mw": TPP_NEW_UNITS_MW,
            "new_tower_m3s": TPP_NEW_TOWER_M3S,
            "new_once_through_m3s": TPP_NEW_ONCE_THROUGH_M3S,
            "capacity_factor": TPP_CAPACITY_FACTOR,
        },
        "lever_bounds": LEVER_BOUNDS,
        "default_levers": asdict(Levers()),
        "historical_plan": asdict(HISTORICAL_PLAN),
        "setting_bounds": SETTING_BOUNDS,
        "default_settings": asdict(Settings()),
        "cards": {cid: asdict(card) for cid, card in CARDS.items()},
        "role_targets": {role: [list(t) for t in targets] for role, targets in ROLE_TARGETS.items()},
        "role_levers": ROLE_LEVERS,
        "objectives": OBJECTIVES,
        "axes": AXES,
        "edges": [f"{s}_to_{t}" for s, t in EDGES],
    }


def build_reference_cases(n: int, seed: int) -> list[dict]:
    """The canonical cases plus seeded random ones, each with every indicator and monthly series, for the JS twin."""
    rng = random.Random(seed)
    cases = list(CANONICAL_CASES)
    while len(cases) < n:
        cases.append(_random_case(rng))
    reference_cases = []
    for settings, cards, year, levers in cases:
        outcome = evaluate(settings, cards, year, levers)
        reference_cases.append(
            {
                "settings": asdict(settings),
                "cards": list(cards),
                "year": year,
                "levers": asdict(levers),
                "indicators": outcome.indicators,
                "monthly": outcome.monthly,
            }
        )
    return reference_cases


def export_game_data(
    path: Path,
    n_reference_cases: int = 30,
    pop_size: int = 300,
    generations: int = 150,
    seed: int = 42,
    fronts: dict[str, tuple[tuple[str, ...], str]] | None = None,
    dense_n: int = 20_000,
) -> None:
    """Write everything the offline HTML game needs, the reference cases for the JavaScript twin and the fronts."""
    reference_cases = build_reference_cases(n_reference_cases, seed)
    front_data = {}
    kept: dict[str, list[FrontMember]] = {}
    for name, (cards, year) in (fronts if fronts is not None else FRONTS).items():
        started = time.perf_counter()
        found = optimise(Settings(), cards, year, pop_size=pop_size, generations=generations, seed=seed)
        wall = time.perf_counter() - started
        members = display_members(found, year)
        kept[name] = members
        front_data[name] = {
            "cards": list(cards),
            "year": year,
            "wall_time_s": round(wall, 1),
            "optimiser_members": len(found),
            "members": [
                {
                    "levers": asdict(mb.levers),
                    "objectives": mb.objectives,
                    "indicators": {y: {k: ind[k] for k in MEMBER_INDICATORS} for y, ind in mb.indicators.items()},
                }
                for mb in members
            ],
        }
        logger.info("%s: %d members in %.0f s", name, len(members), wall)
    data = {
        "meta": {
            "model": "zarafshan_game",
            "title": "Zarafshan water-allocation trade-off game",
            "taqsim_version": importlib.metadata.version("taqsim"),
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
        "fronts": front_data,
        "analysis": analyse(
            {name: [(mb.levers, mb.indicators["dry"]) for mb in members] for name, members in kept.items()},
            dense_n=dense_n,
        ),
    }
    Path(path).write_text(json.dumps(data, separators=(",", ":")))
    logger.info("wrote %s", path)


def default_levers_with(**changes: float) -> Levers:
    return replace(Levers(), **changes)
