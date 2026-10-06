"""River flow for nature vs irrigation: the e-flow game's reference model.

One river reach (the Zarafshan at Ravatkhoja), one headworks with TaqSim's own e-flow rule, one canal that serves the
three Samarkand canals (Dargom, Mirzapay, Akkaradarya), the fields, and the river end. Two levers, both numbers in the
headworks' rule (``EFlowSplit``):

- the **reserve share**: the share of each day's flow that the headworks leaves in the river;
- the **reserve ceiling**: the reserve never exceeds this flow. With a share of 100 % the ceiling is a guaranteed
  minimum flow: the first ``ceiling`` m³/s of every day stay in the river.

Two results per plan: crops supplied (% of the canal's demand over the five scored years) and the river score (fishy's
IARI against the 2010-2023 record at Ravatkhoja; 0 = natural, lower is closer to natural).

Run ``uv run --project workshop/eflow_game python -m eflow_game.model`` to precompute the plan grid.
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import time
import uuid
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

logger = logging.getLogger(__name__)

GAME_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = GAME_DIR.parents[1]
DATA_DIR = REPO_ROOT / "data" / "ZRB_baseline"
INFLOW_FILE = DATA_DIR / "inflow" / "inflow_ravatkhoza_daily_2010_2023.csv"
DEMAND_FILE = DATA_DIR / "demand" / "demand_all_districts_2017-2022_monthly.csv"
DATA_FILE = GAME_DIR / "eflow_game_data.json"

DAY = 86400.0
SAMARKAND_CANALS = ("Dargom_m3s", "Mirzapay_m3s", "Akkaradarya_m3s")
REFERENCE_YEARS = tuple(range(2010, 2024))  # the 14 years of the record; fishy asks for 20
SCORE_YEARS = tuple(range(2019, 2024))  # fishy scores the last five impacted years
REFERENCE_YEARS_REQUIRED_BY_FISHY = 20
RESERVE_SHARES_PCT = tuple(range(0, 101, 10))
CEILINGS_M3S: tuple[float | None, ...] = (10.0, 20.0, 40.0, 60.0, 80.0, 100.0, 150.0, 200.0, None)
NO_CEILING_M3S = 1e9  # TaqSim's cap when the lever says "no ceiling"
STARTING_PLAN = (0, None)  # the canal takes all it needs

# fishy's reason codes, in plain words for the page and the manuals
REASONS = {
    "unsupported_ambiguous_circular_timing_axis": (
        "the date of the lowest flow cannot be scored: in the natural record it falls near the turn of the year, "
        "so the index cannot place the plan's dates on a circular axis"
    ),
    "unsupported_input_parameter": "an indicator is undefined in at least one year",
    "unsupported_required_parameters": "not all 33 indicators could be scored",
}
INDICATOR_GROUPS = {
    1: "Monthly flows (12)",
    2: "Extreme flows: 1- to 90-day minima and maxima, zero-flow days, base flow (12)",
    3: "Timing of the lowest and the highest flow (2)",
    4: "Low and high pulses: count and duration (4)",
    5: "Rate of change: rise, fall, reversals (3)",
}


@dataclass(frozen=True)
class Plan:
    """One setting of the two levers."""

    share_pct: int
    ceiling_m3s: float | None

    @property
    def id(self) -> str:
        return f"s{self.share_pct}_c{'none' if self.ceiling_m3s is None else int(self.ceiling_m3s)}"

    @property
    def name(self) -> str:
        if self.share_pct == 0:
            return "Canal takes all it needs"
        if self.share_pct == 100 and self.ceiling_m3s is None:
            return "River untouched"
        if self.ceiling_m3s is None:
            return f"Leave {self.share_pct} % of each day's flow"
        if self.share_pct == 100:
            return f"First {self.ceiling_m3s:.0f} m³/s always stay"
        return f"Leave {self.share_pct} %, at most {self.ceiling_m3s:.0f} m³/s"

    @property
    def cap_m3s(self) -> float:
        return NO_CEILING_M3S if self.ceiling_m3s is None else self.ceiling_m3s


@dataclass
class YearRun:
    """One plan run for one calendar year: daily flows in m³/s."""

    year: int
    dates: list[date]
    natural: np.ndarray
    river: np.ndarray
    fields: np.ndarray
    seconds: float

    def mass_balance_residual_m3(self) -> float:
        return float(np.round(self.natural * DAY).sum() - (self.river + self.fields).sum() * DAY)


@dataclass
class RiverScore:
    """fishy's IARI for one plan over the scored years."""

    total: float | None
    partial: float
    scored: int
    classification: str | None
    indicators: dict[str, float | None]
    unscorable: dict[str, str]

    @property
    def score(self) -> float:
        """The total when fishy can score all 33 indicators, otherwise the mean of those it can."""
        return self.partial if self.total is None else self.total


@dataclass
class PlanResult:
    plan: Plan
    crops_pct: float
    crops_by_year_pct: dict[int, float]
    river: RiverScore
    warnings: list[str]
    lowest_flow_m3s: float
    seconds: float


def plan_grid() -> list[Plan]:
    """Every lever combination; a share of 0 % is the same plan whatever the ceiling, so it appears once."""
    plans = [Plan(0, None)]
    plans += [Plan(s, c) for s in RESERVE_SHARES_PCT if s > 0 for c in CEILINGS_M3S]
    return plans


@lru_cache(maxsize=1)
def load_inflow() -> pl.DataFrame:
    """The daily Ravatkhoja record 2010-2023, columns date and q (m³/s)."""
    frame = pl.read_csv(INFLOW_FILE, try_parse_dates=True).rename({"Date": "date", "Q_m3s": "q"})
    return frame.with_columns(pl.col("q").cast(pl.Float64)).sort("date")


@lru_cache(maxsize=1)
def demand_curve() -> tuple[float, ...]:
    """Monthly mean 2017-2022 of the three Samarkand canals, m³/s, January first."""
    frame = pl.read_csv(DEMAND_FILE, try_parse_dates=True)
    total = sum(pl.col(c) for c in SAMARKAND_CANALS)
    monthly = (
        frame.with_columns(pl.col("Date").dt.month().alias("m"), total.alias("q")).group_by("m").agg(pl.col("q").mean())
    )
    return tuple(float(v) for v in monthly.sort("m")["q"].to_list())


def demand_daily(dates: list[date] | pl.Series) -> np.ndarray:
    curve = np.array(demand_curve())
    months = np.array([d.month for d in dates])
    return curve[months - 1]


def twin_year(natural: np.ndarray, demand: np.ndarray, plan: Plan) -> tuple[np.ndarray, np.ndarray]:
    """The same two rules in numpy (river, fields in m³/s); checked against TaqSim in the tests."""
    reserve = np.minimum(plan.share_pct / 100 * natural, plan.cap_m3s)
    fields = np.minimum(demand, natural - reserve)
    return natural - fields, fields


def build_system(year: int, plan: Plan, inflow: pl.DataFrame | None = None) -> Any:
    """The five-block TaqSim system for one calendar year under one plan (built, not run)."""
    from taqsim import EFlowSplit, IntervalVolume, Parameter, PriorityDistribution, TimeAxis, WaterSystem, WaterVolume

    inflow = load_inflow() if inflow is None else inflow
    year_frame = inflow.filter(pl.col("date").dt.year() == year)
    series = pl.DataFrame(
        {"time": year_frame["date"].cast(pl.Datetime("us")), "value": (year_frame["q"] * DAY).round(0)}
    )
    system = WaterSystem(
        time=TimeAxis(datetime(year, 1, 1), year_frame.height, "1d"), quantum="1 m3", name="eflow-game"
    )
    system.source("inflow", IntervalVolume(series, "m3", "1d", "1 m3"))
    system.sink("fields")
    system.sink("river_end")
    system.reach(
        "headworks",
        "inflow",
        "canal_gate",
        rule=EFlowSplit(
            natural_ratios={"river_end": 1.0},
            remainder_ratios={"canal_gate": 1.0},
            eflow_fraction=Parameter("reserve_share", plan.share_pct / 100, (0.0, 1.0)),
            eflow_cap=WaterVolume(plan.cap_m3s * DAY, "m3"),
        ),
    )
    system.reach(
        "canal_gate",
        "headworks",
        "fields",
        rule=PriorityDistribution(
            "fields", tuple(WaterVolume(round(v * DAY), "m3") for v in demand_curve()), {"river_end": 1.0}
        ),
    )
    return system.build()


def _run_year_engine(year: int, plan: Plan) -> YearRun:
    """Run one calendar year in TaqSim and return daily flows in m³/s."""
    inflow = load_inflow()
    built = build_system(year, plan, inflow)
    started = time.perf_counter()
    run = built.run(uuid.uuid4().hex)
    seconds = time.perf_counter() - started
    year_frame = inflow.filter(pl.col("date").dt.year() == year)
    river = np.array([w.value for w in run.arrivals("river_end")], dtype=float) / DAY
    fields = np.array([w.value for w in run.arrivals("fields")], dtype=float) / DAY
    return YearRun(year, year_frame["date"].to_list(), year_frame["q"].to_numpy(), river, fields, seconds)


def _job(args: tuple[int, int, float | None]) -> tuple[str, int, list[float], list[float], float]:
    year, share, ceiling = args
    run = run_year(year, Plan(share, ceiling))
    return Plan(share, ceiling).id, year, run.river.tolist(), run.fields.tolist(), run.seconds


def _run_grid_engine(
    plans: list[Plan], years: tuple[int, ...] = SCORE_YEARS, workers: int | None = None
) -> dict[str, dict[int, YearRun]]:
    """Every plan for every year in a process pool (no storage, so the years are independent)."""
    inflow = load_inflow()
    jobs = [(y, p.share_pct, p.ceiling_m3s) for p in plans for y in years]
    workers = workers or os.cpu_count() or 4
    runs: dict[str, dict[int, YearRun]] = {p.id: {} for p in plans}
    with ProcessPoolExecutor(workers) as pool:
        for plan_id, year, river, fields, seconds in pool.map(_job, jobs, chunksize=1):
            year_frame = inflow.filter(pl.col("date").dt.year() == year)
            runs[plan_id][year] = YearRun(
                year,
                year_frame["date"].to_list(),
                year_frame["q"].to_numpy(),
                np.array(river),
                np.array(fields),
                seconds,
            )
    return runs


# ---------- fishy ----------


def _fishy():
    """fishy's IARI module (``import fishy.diagnostics.iari`` gives the function, not the module)."""
    module = importlib.import_module("fishy.diagnostics.iari")
    original = getattr(module, "_years_unpatched", None) or module._years
    module._years_unpatched = original
    # The record has 14 years; fishy hard-codes 20. The lead decided to use the available data (2026-10-05).
    module._years = lambda frame, minimum: original(frame, min(minimum, len(REFERENCE_YEARS)))
    return module


@lru_cache(maxsize=1)
def iha_profile():
    from fishy.diagnostics.iha import CentralStatistic, IHAProfile, PulseThresholds, RateBoundary
    from fishy.quantities import Flow

    q = load_inflow()["q"].to_numpy()
    low, high = (float(v) for v in np.percentile(q, [25, 75]))
    return IHAProfile(CentralStatistic.MEAN, PulseThresholds(Flow(low), Flow(high)), RateBoundary.WITHIN_YEAR)


def pulse_thresholds_m3s() -> tuple[float, float]:
    q = load_inflow()["q"].to_numpy()
    return tuple(float(v) for v in np.percentile(q, [25, 75]))


def annual_table(dates: list[date], flow_m3s: np.ndarray) -> pl.DataFrame:
    from fishy.diagnostics.iha import annual_indicators

    frame = pl.DataFrame(
        {"date": dates, "discharge_m3_s": flow_m3s.astype(float)},
        schema={"date": pl.Date, "discharge_m3_s": pl.Float64},
    )
    return annual_indicators(frame, iha_profile())


@lru_cache(maxsize=1)
def natural_table() -> pl.DataFrame:
    inflow = load_inflow()
    return annual_table(inflow["date"].to_list(), inflow["q"].to_numpy())


def score_river(dates: list[date], river_m3s: np.ndarray) -> RiverScore:
    """IARI of the river below the headworks against the natural record (median summary, linear quantiles)."""
    fi = _fishy()
    impacted = annual_table(dates, river_m3s)
    result = fi.iari(
        natural_table(), impacted, summary=fi.SummaryStatistic.MEDIAN, quantile=fi.QuantileEstimator.LINEAR
    )
    rows = result.scores.select("parameter", "score", "reason").iter_rows()
    indicators: dict[str, float | None] = {}
    unscorable: dict[str, str] = {}
    for parameter, score, reason in rows:
        indicators[parameter] = None if score is None else float(score)
        if score is None:
            unscorable[parameter] = reason or "unscorable"
    scored = [v for v in indicators.values() if v is not None]
    return RiverScore(
        total=None if result.total is None else float(result.total),
        partial=float(np.mean(scored)) if scored else float("nan"),
        scored=len(scored),
        classification=result.classification.value if result.classification else None,
        indicators=indicators,
        unscorable=unscorable,
    )


def plain_reason(code: str) -> str:
    parts = [p.strip() for p in code.split(";")]
    words = [REASONS.get(p, p.replace("_", " ")) for p in parts]
    return "; ".join(dict.fromkeys(words))


def warnings_for(runs: dict[int, YearRun], score: RiverScore) -> list[str]:
    """Visible warnings: what the score leaves out and what the river went through."""
    notes = []
    if score.total is None:
        names = ", ".join(score.unscorable)
        notes.append(
            f"{len(score.unscorable)} of 33 indicators could not be scored ({names}); the score is the mean of the other {score.scored}"
        )
        for parameter, reason in score.unscorable.items():
            notes.append(f"{parameter.replace('_', ' ')}: {plain_reason(reason)}")
    natural_min = float(load_inflow()["q"].min())
    below = sum(int((r.river < natural_min - 1e-9).sum()) for r in runs.values())
    if below:
        notes.append(
            f"river below the lowest natural flow on record ({natural_min:.1f} m³/s) on {below} of {sum(len(r.river) for r in runs.values())} days"
        )
    dry = sum(int((r.river <= 1e-9).sum()) for r in runs.values())
    if dry:
        notes.append(f"river dry on {dry} days")
    return notes


def evaluate_plan(plan: Plan, runs: dict[int, YearRun]) -> PlanResult:
    years = sorted(runs)
    dates = [d for y in years for d in runs[y].dates]
    river = np.concatenate([runs[y].river for y in years])
    fields = np.concatenate([runs[y].fields for y in years])
    demand = demand_daily(dates)
    by_year = {y: 100 * float(runs[y].fields.sum() / demand_daily(runs[y].dates).sum()) for y in years}
    score = score_river(dates, river)
    return PlanResult(
        plan=plan,
        crops_pct=100 * float(fields.sum() / demand.sum()),
        crops_by_year_pct=by_year,
        river=score,
        warnings=warnings_for(runs, score),
        lowest_flow_m3s=float(river.min()),
        seconds=sum(runs[y].seconds for y in years),
    )


# ---------- the trade-off ----------


def dominates(a: tuple[float, float], b: tuple[float, float]) -> bool:
    """(crops, score): higher crops and lower score are better; a beats b if no worse on both and better on one."""
    return a[0] >= b[0] - 1e-9 and a[1] <= b[1] + 1e-9 and (a[0] > b[0] + 1e-9 or a[1] < b[1] - 1e-9)


def plan_entry(r: PlanResult) -> dict[str, Any]:
    """The exported record of one plan, rounded to the precision the page shows and compares."""
    return {
        "id": r.plan.id,
        "name": r.plan.name,
        "share_pct": r.plan.share_pct,
        "ceiling_m3s": r.plan.ceiling_m3s,
        "crops_pct": round(r.crops_pct, 3),
        "crops_by_year_pct": {str(y): round(v, 3) for y, v in r.crops_by_year_pct.items()},
        "score": round(r.river.score, 5),
        "score_is_total": r.river.total is not None,
        "scored": r.river.scored,
        "classification": r.river.classification,
        "indicators": {k: None if v is None else round(v, 4) for k, v in r.river.indicators.items()},
        "unscorable": r.river.unscorable,
        "warnings": r.warnings,
        "lowest_flow_m3s": round(r.lowest_flow_m3s, 3),
    }


def mark_unbeaten(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Set ``unbeaten`` and ``beaten_by`` on the stored values, so that the page's own check agrees exactly.

    Plans with the same two results do not beat one another: every one of them is unbeaten when nothing else beats it.
    """
    for e in entries:
        own = (e["crops_pct"], e["score"])
        e["beaten_by"] = [o["id"] for o in entries if o is not e and dominates((o["crops_pct"], o["score"]), own)]
        e["unbeaten"] = not e["beaten_by"]
    return entries


def distinct_unbeaten_outcomes(entries: list[dict[str, Any]]) -> int:
    return len({(e["crops_pct"], e["score"]) for e in entries if e["unbeaten"]})


def is_share_only(e: dict[str, Any]) -> bool:
    return e["ceiling_m3s"] is None and 0 < e["share_pct"] < 100


def is_minimum_only(e: dict[str, Any]) -> bool:
    return e["share_pct"] == 100 and e["ceiling_m3s"] is not None


def teaching_pair(
    entries: list[dict[str, Any]], tolerance_pct: float = 3.0
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """A share-only plan A and a minimum-only plan B with crop supply within the tolerance.

    Preferred: B beats A outright (no fewer crops, better score), widest score gap. Otherwise the widest gap among
    pairs whose A gives the crops less than 99.5 %.
    """
    shares = [e for e in entries if is_share_only(e)]
    minima = [e for e in entries if is_minimum_only(e)]
    candidates = [
        (a, b)
        for a in shares
        for b in minima
        if abs(a["crops_pct"] - b["crops_pct"]) <= tolerance_pct and a["crops_pct"] < 99.5
    ]
    beating = [(a, b) for a, b in candidates if dominates((b["crops_pct"], b["score"]), (a["crops_pct"], a["score"]))]
    pool = beating or candidates
    if not pool:
        return None
    return max(pool, key=lambda ab: ab[0]["score"] - ab[1]["score"])


# ---------- export ----------


def _series_payload(runs: dict[str, dict[int, YearRun]]) -> dict[str, Any]:
    first = next(iter(runs.values()))
    years = sorted(first)
    return {
        "years": years,
        "dates": [d.isoformat() for y in years for d in first[y].dates],
        "natural_m3s": [round(float(v), 2) for y in years for v in first[y].natural],
    }


def finish_export(payload: dict[str, Any]) -> dict[str, Any]:
    """Mark the unbeaten plans, choose the teaching pair and fill the derived counts; needs no TaqSim run."""
    entries = mark_unbeaten(payload["plans"])
    pair = teaching_pair(entries)
    payload["meta"]["unbeaten"] = sum(e["unbeaten"] for e in entries)
    payload["meta"]["unbeaten_outcomes"] = distinct_unbeaten_outcomes(entries)
    payload["meta"]["starting_plan"] = Plan(*STARTING_PLAN).id
    payload["meta"]["teaching_pair"] = None if pair is None else [pair[0]["id"], pair[1]["id"]]
    return payload


def export_game_data(
    path: Path = DATA_FILE, workers: int | None = None, plans: list[Plan] | None = None
) -> dict[str, Any]:
    """Run the grid, score every plan, mark the unbeaten ones and write the JSON the page and the notebook read."""
    plans = plan_grid() if plans is None else plans
    started = time.perf_counter()
    runs = run_grid(plans, workers=workers)
    wall_runs = time.perf_counter() - started
    results = [evaluate_plan(p, runs[p.id]) for p in plans]
    wall = time.perf_counter() - started
    run_seconds = [r.seconds for p in plans for r in runs[p.id].values()]
    low, high = pulse_thresholds_m3s()
    curve = demand_curve()
    payload = {
        "meta": {
            "title": "River flow for nature vs irrigation",
            "built": datetime.now().isoformat(timespec="seconds"),
            "taqsim": _version("taqsim"),
            "fishy": "881660e",
            "reference_years": list(REFERENCE_YEARS),
            "reference_years_required_by_fishy": REFERENCE_YEARS_REQUIRED_BY_FISHY,
            "score_years": list(SCORE_YEARS),
            "runs": len(run_seconds),
            "mean_run_seconds": float(np.mean(run_seconds)),
            "wall_seconds_runs": wall_runs,
            "wall_seconds_total": wall,
            "workers": workers or os.cpu_count(),
            "plans": len(plans),
            "inflow_file": str(INFLOW_FILE.relative_to(REPO_ROOT)),
            "demand_file": str(DEMAND_FILE.relative_to(REPO_ROOT)),
            "pulse_thresholds_m3s": [low, high],
            "natural_min_m3s": float(load_inflow()["q"].min()),
            "natural_mean_m3s": float(load_inflow()["q"].mean()),
            "demand_mean_m3s": float(np.mean(curve)),
            "demand_mm3_per_year": float(np.mean(curve) * DAY * 365.25 / 1e6),
            "iari_classes": {"elevato": 0.05, "buono": 0.15},
        },
        "levers": {"shares_pct": list(RESERVE_SHARES_PCT), "ceilings_m3s": list(CEILINGS_M3S)},
        "demand_curve_m3s": list(curve),
        "indicator_groups": {str(k): v for k, v in INDICATOR_GROUPS.items()},
        "series": _series_payload(runs),
        "plans": [plan_entry(r) for r in results],
    }
    finish_export(payload)
    path.write_text(json.dumps(payload, separators=(",", ":")))
    logger.info(
        "wrote %s: %d plans, %d unbeaten, %d runs, %.1f s per run, %.0f s wall",
        path,
        len(plans),
        payload["meta"]["unbeaten"],
        len(run_seconds),
        payload["meta"]["mean_run_seconds"],
        wall,
    )
    return payload


def refresh_export(path: Path = DATA_FILE) -> dict[str, Any]:
    """Recompute the derived parts of an existing export (unbeaten flags, pair, counts) without re-running TaqSim."""
    payload = finish_export(json.loads(path.read_text()))
    path.write_text(json.dumps(payload, separators=(",", ":")))
    return payload


def _version(package: str) -> str:
    try:
        from importlib.metadata import version

        return version(package)
    except Exception:  # noqa: BLE001 - version is informational only
        return "unknown"


def result_summary(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Flat rows of the exported plans for tables in the notebook and the manuals."""
    return [
        {
            k: p[k]
            for k in (
                "id",
                "name",
                "share_pct",
                "ceiling_m3s",
                "crops_pct",
                "score",
                "score_is_total",
                "classification",
                "unbeaten",
            )
        }
        for p in payload["plans"]
    ]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    export_game_data()
    logger.info(json.dumps(json.loads(DATA_FILE.read_text())["meta"], indent=1))


# Course build: without the Rust engine (Google Colab) these replay the runs recorded in eflow_game_runs.json.
from eflow_game.replay import engine_note, run_grid, run_year  # noqa: E402,F401
