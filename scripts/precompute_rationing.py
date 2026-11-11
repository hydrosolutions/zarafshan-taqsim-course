"""Run the heavy parts of the rationing lesson once and store the score tables for the block editor.

    python scripts/precompute_rationing.py          # only the tables that are not stored yet
    python scripts/precompute_rationing.py --all    # everything again (about 15 minutes)

The grids (441 plans, 861 winter plans for each forecast skill) and the optimizer take minutes in Colab and far
longer in the browser, so the editor reads them from `block_editor/precomputed.json`. They are computed with
the lesson's standard numbers; the calls are the ones of `02_rationing_en.ipynb`. The tables whose names start
with `grid_capacity`, `grid_seed`, `found_years`, `found_seasonal`, `cautious` and `late` belong to the six
exercises at the end of the coursebook.
"""

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from taqsim import Objective, Sink, Source, Storage, TimeSeries, WaterSystem, optimize
from taqsim import Demand, Edge
from taqsim.node import NoLoss
from taqsim.time import Frequency

from zarafshan_taqsim import rationing_coursebook as rc
from zarafshan_taqsim.block_editor import rules

OUT = Path(__file__).resolve().parents[1] / "src" / "zarafshan_taqsim" / "block_editor" / "precomputed.json"
SKILLS = (0.0, 0.3, 0.5, 0.65, 0.8, 0.9, 1.0)
EXERCISE_SKILLS = (0.3, 0.5, 0.65, 0.8, 0.9, 1.0)
CAPACITIES = (60.0, 80.0)
CAUTION = 0.7  # exercise 5: the share of the forecast a cautious operator counts
OTHER_SEED = 1  # exercise 3


def _with_capacity(capacity: float) -> None:
    rc.configure(capacity=capacity)
    for rule in (rc.RationingRelease, rules.SeasonalRationing):  # a larger reservoir may have a higher trigger
        rule.__bounds__ = {**rule.__bounds__, "trigger": (0.0, capacity)}


def _seasonal_system(inflows: tuple[float, ...], policy: rules.SeasonalRationing) -> WaterSystem:
    """The four-block system of the lesson with the two-ration rule on the reservoir."""
    years = len(inflows) // 12
    system = WaterSystem(frequency=Frequency.MONTHLY)
    system.add_node(Source(id="river", inflow=TimeSeries(values=list(inflows))))
    system.add_node(Storage(id="reservoir", capacity=rc.CAPACITY_MM3, initial_storage=rc.START_STORAGE_MM3, release_policy=policy, loss_rule=NoLoss()))
    system.add_node(Demand(id="farm", requirement=TimeSeries(values=list(rc.MONTHLY_NEED_MM3) * years)))
    system.add_node(Sink(id="downstream"))
    for source, target in rc.NETWORK_EDGES:
        system.add_edge(Edge(id=f"{source}_to_{target}", source=source, target=target))
    system.validate()
    return system


def _years_short(system: WaterSystem) -> float:
    return float(rc._scores(rc.shortage_by_month(system)).years_short)


def compute(name: str):
    inflows = rc.synthetic_inflows()
    if name == "grid":
        table = rc.score_plans(inflows, rc.plan_grid())
    elif name == "found":
        table = rc.optimise_plans(inflows, pop_size=40, generations=40, seed=42)
    elif name == "paper_grid":
        table = rc.score_plans(rc.synthetic_inflows(regime=rc.PAPER_REGIME), rc.plan_grid())
    elif name == "evaporation_grid":
        table = rc.score_plans(inflows, rc.plan_grid(), evaporation_share=rc.EVAPORATION_SHARE_EXAMPLE)
    elif name == "storage_only":
        table = rc.score_winter_plans(inflows, rc.winter_grid(n_trigger=41, trigger_max=rc.CAPACITY_MM3))
    elif name.startswith("skill_"):  # winter plans that see a forecast of that skill
        skill = float(name.split("_")[1])
        table = rc.score_winter_plans(inflows, rc.winter_grid(n_trigger=41), forecast=rc.seasonal_forecast(inflows, skill))
    # --- the exercises
    elif name.startswith("grid_capacity_"):  # 1: a bigger reservoir, triggers from 0 to its capacity
        _with_capacity(float(name.rsplit("_", 1)[1]))
        table = rc.score_plans(inflows, rc.plan_grid())
    elif name == "found_years":  # 2: the optimizer with "years short" as its second goal
        goals = [rc.objectives()[0], Objective(name="years_short", direction="minimize", evaluate=_years_short)]
        result = optimize(system=rc.build_system(inflows), objectives=goals, timesteps=len(inflows), pop_size=40, generations=40, seed=42)
        plans = [rc.Plan(float(np.clip(rc._parameter(s.parameters, "trigger"), 0.0, rc.CAPACITY_MM3)), float(np.clip(rc._parameter(s.parameters, "ration"), 0.0, 1.0))) for s in result]
        table = rc.score_plans(inflows, plans)
    elif name == f"grid_seed_{OTHER_SEED}":  # 3: another hundred years of the same river
        table = rc.score_plans(rc.synthetic_inflows(seed=OTHER_SEED), rc.plan_grid())
    elif name == f"paper_grid_seed_{OTHER_SEED}":
        table = rc.score_plans(rc.synthetic_inflows(seed=OTHER_SEED, regime=rc.PAPER_REGIME), rc.plan_grid())
    elif name == "found_seasonal":  # 4: the optimizer with a ration for early and one for late summer
        result = optimize(system=_seasonal_system(inflows, rules.SeasonalRationing()), objectives=rc.objectives(), timesteps=len(inflows), pop_size=40, generations=40, seed=42)
        rows = []
        for solution in result:
            trigger = float(np.clip(rc._parameter(solution.parameters, "trigger"), 0.0, rc.CAPACITY_MM3))
            late = float(np.clip(rc._parameter(solution.parameters, "ration_late"), 0.0, 1.0))
            early = float(np.clip(next(value for path, value in solution.parameters.items() if path.endswith("ration")), 0.0, 1.0))
            system = _seasonal_system(inflows, rules.SeasonalRationing(trigger=trigger, ration=early, ration_late=late))
            system.simulate(len(inflows))
            scores = rc._scores(rc.shortage_by_month(system))
            rows.append((trigger, early, late, scores.mean_shortage, scores.worst_month, scores.years_short))
        table = pd.DataFrame(rows, columns=["trigger", "ration", "ration_late", "mean_shortage", "worst_month", "years_short"])
        table["unbeaten"] = rc.unbeaten(table[list(rc.GOALS)].to_numpy().round(6))
        table = table.sort_values(list(rc.GOALS)).reset_index(drop=True)
    elif name.startswith("cautious_"):  # 5: the rule counts only part of the forecast
        skill = float(name.split("_")[1])
        forecast = tuple(CAUTION * value for value in rc.seasonal_forecast(inflows, skill))
        table = rc.score_winter_plans(inflows, rc.winter_grid(n_trigger=41), forecast=forecast)
    elif name.startswith("late_"):  # 6: the forecast only exists in the last two winter months
        skill = float(name.split("_")[1])
        rc.WinterRelease = rules.LateForecastRelease  # `build_system` then builds the late rule (this process only)
        table = rc.score_winter_plans(inflows, rc.winter_grid(n_trigger=41), forecast=rc.seasonal_forecast(inflows, skill))
    else:
        raise KeyError(name)
    return name, {"columns": list(table.columns), "data": json.loads(table.round(6).to_json(orient="values"))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="compute every table again, not only the missing ones")
    everything = parser.parse_args().all
    names = ["grid", "found", "paper_grid", "evaporation_grid", "storage_only", *(f"skill_{skill:g}" for skill in SKILLS)]
    names += [f"grid_capacity_{capacity:g}" for capacity in CAPACITIES]
    names += ["found_years", f"grid_seed_{OTHER_SEED}", f"paper_grid_seed_{OTHER_SEED}", "found_seasonal"]
    names += [f"{kind}_{skill:g}" for kind in ("cautious", "late") for skill in EXERCISE_SKILLS]
    tables = {} if everything or not OUT.exists() else json.loads(OUT.read_text(encoding="utf-8"))["tables"]
    todo = [name for name in names if name not in tables]
    started = time.perf_counter()
    # one table per process: each process sets the reservoir size or the rule it needs and is then thrown away
    with ProcessPoolExecutor(max_workers=4, max_tasks_per_child=1) as pool:
        for name, table in pool.map(compute, todo):
            tables[name] = table
            print(f"{name}: {len(table['data'])} rows ({time.perf_counter() - started:.0f} s)", flush=True)
    settings = {
        "capacity": rc.CAPACITY_MM3,
        "start_storage": rc.START_STORAGE_MM3,
        "summer_need": rc.SUMMER_NEED_MM3,
        "winter_need": rc.WINTER_NEED_MM3,
        "years": rc.YEARS,
        "seed": rc.SEED,
        "evaporation_share": rc.EVAPORATION_SHARE_EXAMPLE,
        "summer_plan_for_winter": [rc.SUMMER_PLAN_FOR_WINTER.trigger, rc.SUMMER_PLAN_FOR_WINTER.ration],
        "caution": CAUTION,
        "other_seed": OTHER_SEED,
    }
    OUT.write_text(json.dumps({"settings": settings, "tables": {name: tables[name] for name in names}}, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT.name}: {OUT.stat().st_size / 1024:.0f} KB, {len(names)} tables, {len(todo)} computed now")


if __name__ == "__main__":
    main()
