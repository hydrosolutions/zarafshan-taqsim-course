"""Replay of recorded TaqSim runs for the e-flow notebook when the Rust engine is not installed (Google Colab).

The course build renames the engine functions in ``model.py`` to ``_run_year_engine`` and ``_run_grid_engine`` and
re-exports ``run_year`` and ``run_grid`` from here. With the engine present they behave exactly as before. Without it,
they return the runs recorded in ``eflow_game_runs.json`` by ``record_runs`` and raise a clear error for anything that
was not recorded.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path

import numpy as np

RUNS_FILE = Path(__file__).resolve().parents[2] / "eflow_game_runs.json"


def engine_available() -> bool:
    """True when the new TaqSim (Rust engine) can be imported."""
    try:
        from taqsim import EFlowSplit, IntervalVolume  # noqa: F401
    except ImportError:
        return False
    return True


def _store() -> dict:
    if not RUNS_FILE.exists():
        raise RuntimeError(
            f"TaqSim's engine is not installed and no recorded runs were found at {RUNS_FILE}. "
            "Run the notebook where the new TaqSim is installed, or record the runs with record_runs()."
        )
    return json.loads(RUNS_FILE.read_text(encoding="utf-8"))


def _replay(year: int, plan):
    from eflow_game import model as m

    store = _store()
    key = f"{plan.id}|{year}"
    if key not in store["runs"]:
        raise RuntimeError(
            f"No recorded run for plan {plan.name!r} in {year}. Recorded: {sorted(store['runs'])}. "
            "Install the new TaqSim to run other plans, or add this one with record_runs()."
        )
    entry = store["runs"][key]
    inflow = m.load_inflow()
    year_frame = inflow.filter(inflow["date"].dt.year() == year)
    return m.YearRun(
        year,
        year_frame["date"].to_list(),
        year_frame["q"].to_numpy(),
        np.array(entry["river"], dtype=float),
        np.array(entry["fields"], dtype=float),
        float(entry["seconds"]),
    )


def run_year(year: int, plan):
    """Run one calendar year in TaqSim, or replay the recorded run when the engine is absent."""
    from eflow_game import model as m

    if engine_available():
        return m._run_year_engine(year, plan)
    return _replay(year, plan)


def run_grid(plans, years=None, workers=None):
    """Every plan for every year: in a process pool with the engine, from the recording without it."""
    from eflow_game import model as m

    years = m.SCORE_YEARS if years is None else years
    if engine_available():
        return m._run_grid_engine(plans, years, workers)
    return {p.id: {y: _replay(y, p) for y in years} for p in plans}


def engine_note() -> str:
    """One sentence for the notebook saying whether the run above was live or replayed."""
    if engine_available():
        return "**Computed live by TaqSim's engine.**"
    meta = _store()["meta"]
    return (
        f"**Replayed from a run recorded with TaqSim on {meta['recorded'][:10]}** ({meta['machine']}): "
        "the new TaqSim needs a Rust compiler, which Google Colab does not have, so the run is not repeated here. "
        "Everything below it, including fishy's scoring, runs live."
    )


def record_runs(plan_years: list[tuple[object, int]], machine: str, path: Path = RUNS_FILE) -> dict:
    """Run the given (plan, year) pairs with the engine and write them to ``path`` for later replay."""
    from eflow_game import model as m

    if not engine_available():
        raise RuntimeError("record_runs needs the new TaqSim installed")
    runs = {}
    for plan, year in plan_years:
        run = m._run_year_engine(year, plan)
        runs[f"{plan.id}|{year}"] = {
            "plan": plan.name,
            "year": year,
            "river": [round(float(v), 6) for v in run.river],
            "fields": [round(float(v), 6) for v in run.fields],
            "seconds": round(run.seconds, 3),
        }
    payload = {
        "meta": {
            "recorded": datetime.now().isoformat(timespec="seconds"),
            "machine": machine,
            "taqsim": m._version("taqsim"),
            "incidence": m._version("incidence"),
            "runs": len(runs),
            "mean_run_seconds": float(np.mean([r["seconds"] for r in runs.values()])),
        },
        "runs": runs,
    }
    path.write_text(json.dumps(payload, indent=None, separators=(",", ":")), encoding="utf-8")
    return payload


__all__ = ["engine_available", "engine_note", "record_runs", "run_grid", "run_year"]

_ = (date, os)  # keep the imports for type hints used by callers
