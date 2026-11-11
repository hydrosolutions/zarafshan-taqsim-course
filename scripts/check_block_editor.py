"""Check that a drawing in the block editor gives the same numbers as the coding notebook.

Run it in an environment that has taqsim, anywidget and the builder wheel (or `src` on the path):

    python scripts/check_block_editor.py
"""

import time

import matplotlib

matplotlib.use("Agg")  # draw to memory; no window

from zarafshan_taqsim import rationing_coursebook as rc
from zarafshan_taqsim.block_editor import compile as bc
from zarafshan_taqsim.block_editor import i18n
from zarafshan_taqsim.block_editor import lessons, rules, sandbox
from zarafshan_taqsim.block_editor.widget import BlockEditor

STEP = {step["key"]: index for index, step in enumerate(lessons.STEPS)}


def same(a: rc.Scores, b: rc.Scores) -> bool:
    return abs(a.mean_shortage - b.mean_shortage) < 1e-9 and abs(a.worst_month - b.worst_month) < 1e-9 and a.years_short == b.years_short


def drawing(step: str, **reservoir) -> dict:
    """The step's network with the step's fixed numbers, and these settings on the reservoir."""
    graph = lessons.solution(STEP[step])
    next(node for node in graph["nodes"] if node["id"] == "reservoir")["params"].update(reservoir)
    return lessons.locked(graph, lessons.STEPS[STEP[step]])


def main() -> None:
    inflows = rc.synthetic_inflows()

    # Step 1: river → farm → outlet equals the notebook's run without a reservoir
    mine = lessons.run(lessons.solution(STEP["river_farm"]))
    assert mine.spilled is None and same(mine.result.scores, rc.simulate_without_reservoir(inflows).scores), "step 1 differs"

    # Step 2: with the reservoir, no rationing
    mine = lessons.run(lessons.locked(lessons.solution(STEP["reservoir"]), lessons.STEPS[STEP["reservoir"]]))
    assert same(mine.result.scores, rc.simulate_plan(inflows, rc.NO_RATIONING).scores) and mine.spilled > 0, "step 2 differs"

    # Step 3: the notebook's three plans and the learner's cell
    for trigger, ration in ((16, 0.8), (16, 0.5), (22, 0.55)):
        started = time.perf_counter()
        mine = lessons.run(drawing("rationing", trigger=trigger, ration=ration))
        seconds = time.perf_counter() - started
        theirs = rc.simulate_plan(inflows, rc.Plan(trigger, ration))
        assert same(mine.result.scores, theirs.scores) and (mine.result.storage == theirs.storage).all(), f"plan {trigger}, {ration} differs"
        print(f"plan trigger={trigger} ration={ration}: {mine.result.scores}  ({seconds:.2f} s)")

    # Step 6: the other river and evaporation
    graph = drawing("other_river", trigger=16, ration=0.5, evaporation=0.03)
    paper = rc.synthetic_inflows(regime=rc.PAPER_REGIME)
    assert bc.regime_of(graph).name == "paper"
    assert same(lessons.run(graph).result.scores, rc.simulate_plan(paper, rc.Plan(16, 0.5), evaporation_share=0.03).scores), "step 6 differs"

    # Step 7: the winter fields, served in full and held back (the notebook's runs A and B)
    for winter in (rc.WINTER_IN_FULL, rc.WinterPlan(trigger=24.0, ration=0.0)):
        mine = lessons.run(drawing("winter", winter_trigger=winter.trigger, winter_ration=winter.ration))
        assert mine.winter == rc.simulate_winter(inflows, winter).scores, f"winter plan {winter} differs"

    # Step 8: a winter rule that sees a forecast
    for skill in ("1", "0.5"):
        mine = lessons.run(drawing("forecast", winter_trigger=70, winter_ration=0.0, forecast=skill))
        theirs = rc.simulate_winter(inflows, rc.WinterPlan(70.0, 0.0), forecast=rc.seasonal_forecast(inflows, float(skill)))
        assert mine.winter == theirs.scores, f"forecast skill {skill} differs"

    # The stored tables are the notebook's: spot-check rows of each against a fresh run
    grid = lessons.table("grid")
    for row in grid.sample(4, random_state=1).itertuples():
        fresh = rc.simulate_plan(inflows, rc.Plan(row.trigger, row.ration)).scores
        assert abs(fresh.mean_shortage - row.mean_shortage) < 1e-5 and abs(fresh.worst_month - row.worst_month) < 1e-5, "grid differs"
    for name, forecast in (("storage_only", None), ("skill_0.8", rc.seasonal_forecast(inflows, 0.8))):
        for row in lessons.table(name).sample(3, random_state=2).itertuples():
            fresh = rc.simulate_winter(inflows, rc.WinterPlan(row.winter_trigger, row.winter_ration), forecast=forecast).scores
            assert abs(fresh.summer_shortage - row.summer_shortage) < 1e-5 and abs(fresh.winter_shortage - row.winter_shortage) < 1e-5, f"{name} differs"
    assert len(grid) == 441 and len(lessons.table("skill_1")) == 861 and int(grid["unbeaten"].sum()) == int(rc.unbeaten(grid[list(rc.GOALS)].to_numpy().round(6)).sum())

    # The code shown to the learner builds the same system, with and without the winter fields
    for graph in (drawing("rationing", trigger=16, ration=0.5), drawing("forecast", winter_trigger=70, winter_ration=0.0, forecast="0.8")):
        scope: dict = {}
        exec(bc.to_python(graph), scope)
        shown = rc._scores(rc.shortage_by_month(scope["system"]))
        assert same(shown, lessons.run(graph).result.scores), "the shown code gives other numbers"

    # Other sizes: a changed capacity and need reach the model (steps 1 to 3 only)
    graph = lessons.solution(STEP["reservoir"])
    graph["nodes"][1]["params"].update(capacity=80, initial_storage=100)
    graph["nodes"][2]["params"].update(summer_need=60)
    lessons.run(graph)
    assert rc.CAPACITY_MM3 == 80 and rc.START_STORAGE_MM3 == 80 and rc.SUMMER_NEED_MM3 == 60
    # ... and a larger reservoir may carry a trigger above the standard 40 Mm³
    graph["nodes"][1]["params"].update(capacity=100, initial_storage=20, trigger=82, ration=0.5)
    high = lessons.evaluate(graph, STEP["rationing"], "en")
    assert high["done"] and high["figures"], high["messages"]
    lessons.run(drawing("many_plans"))
    assert rc.CAPACITY_MM3 == 40 and rc.SUMMER_NEED_MM3 == 45, "a later step must put the standard sizes back"

    # The sandbox: every kind of block in one network; all water is accounted for, block by block and in total
    example = sandbox.example()
    system = sandbox.build(example)
    system.simulate(12 * sandbox.YEARS)
    rows = sandbox.balance(example, system)
    assert all(abs(row["closes"]) < 1e-6 for row in rows), [(row["block"], row["closes"]) for row in rows]
    river = sum(row["in"] for row in rows if row["kind"] == "Source")
    gone = sum(row["in"] for row in rows if row["kind"] == "Sink") + sum(row[key] for row in rows for key in ("used", "lost", "left", "stored"))
    assert river > 0 and abs(river - gone) < 1e-6, (river, gone)
    scope = {}
    exec(sandbox.to_python(example), scope)
    assert sandbox.balance(example, scope["system"]) == rows, "the sandbox's shown code gives other numbers"
    # ... a single farm behind a reservoir is the lesson's four-block system, rule and all
    four = lessons.solution(STEP["rationing"])
    four["nodes"][1]["params"].update(trigger=16, ration=0.5)
    system = sandbox.build(four)
    system.simulate(12 * sandbox.YEARS)
    farm = sandbox.demand_run(four["nodes"][2], system).scores
    assert same(farm, rc.simulate_plan(inflows, rc.Plan(16, 0.5)).scores), "the sandbox's general rule differs from the lesson's"
    # ... and what the last guided step leaves on the canvas runs as it is
    shown = lessons.evaluate(lessons.solution(STEP["forecast"]), 0, "en", "sandbox")
    assert shown["figures"] and shown["table"] and shown["cards"][-1]["value"] == "0.0 Mm³", shown["messages"]
    assert not lessons.evaluate({"nodes": example["nodes"], "edges": example["edges"][:-1]}, 0, "en", "sandbox")["figures"]
    assert "sandbox" not in STEP and lessons.lesson("en", "sandbox")["steps"][0]["sandbox"], "the sandbox is a lesson of its own"

    # The exercises: each changed setting reaches the model, and gives what the notebook's functions give
    plan = rc.Plan(30.0, 0.6)
    mine = lessons.run(drawing("ex_capacity", capacity="60", trigger=30, ration=0.6))  # 1: a bigger reservoir
    assert rc.CAPACITY_MM3 == 60 and same(mine.result.scores, rc.simulate_plan(inflows, plan).scores), "exercise 1 differs"
    row = lessons.table("grid_capacity_60").query("trigger == 30 and ration == 0.6").iloc[0]
    assert abs(row.mean_shortage - mine.result.scores.mean_shortage) < 1e-5 and lessons.table("grid_capacity_80")["trigger"].max() == 80
    rc.configure(capacity=40)
    graph = drawing("ex_river", trigger=16, ration=0.5)  # 3: another hundred years, on both rivers
    for regime in (rc.CENTRAL_ASIA_REGIME, rc.PAPER_REGIME):
        graph["nodes"][0]["params"].update(regime=regime.name)
        other = rc.synthetic_inflows(seed=1, regime=regime)
        assert same(lessons.run(graph).result.scores, rc.simulate_plan(other, rc.Plan(16, 0.5)).scores), "exercise 3 differs"
        row = lessons.table("grid_seed_1" if regime is rc.CENTRAL_ASIA_REGIME else "paper_grid_seed_1").query("trigger == 16 and ration == 0.5").iloc[0]
        assert abs(row.mean_shortage - lessons.run(graph).result.scores.mean_shortage) < 1e-5, "the stored grid of exercise 3 differs"
    rc.configure(seed=72)
    same_rations = lessons.run(drawing("ex_seasonal", trigger=16, ration=0.5, ration_late=0.5))  # 4: two equal rations are the old rule
    assert same(same_rations.result.scores, rc.simulate_plan(inflows, rc.Plan(16, 0.5)).scores), "exercise 4 differs"
    for row in lessons.table("found_seasonal").sample(3, random_state=3).itertuples():
        fresh = lessons.run(drawing("ex_seasonal", trigger=row.trigger, ration=row.ration, ration_late=row.ration_late)).result.scores
        # the table stores its settings to six decimals, which moves the scores a little
        assert abs(fresh.mean_shortage - row.mean_shortage) < 1e-3 and abs(fresh.worst_month - row.worst_month) < 1e-2, "the stored optimizer result of exercise 4 differs"
    for skill in ("0.5", "1"):  # 5: the rule counts 70 % of the forecast
        mine = lessons.run(drawing("ex_cautious", forecast=skill, caution=True, winter_trigger=70, winter_ration=0.0))
        counted = tuple(0.7 * value for value in rc.seasonal_forecast(inflows, float(skill)))
        assert mine.winter == rc.simulate_winter(inflows, rc.WinterPlan(70.0, 0.0), forecast=counted).scores, "exercise 5 differs"
        row = lessons.table(f"cautious_{float(skill):g}").query("winter_trigger == 72 and winter_ration == 0.5").iloc[0]
        fresh = rc.simulate_winter(inflows, rc.WinterPlan(72.0, 0.5), forecast=counted).scores
        assert abs(fresh.winter_shortage - row.winter_shortage) < 1e-5, "the stored table of exercise 5 differs"
    late = lessons.run(drawing("ex_late", forecast="1", late_forecast=True, winter_trigger=70, winter_ration=0.0))  # 6: a late forecast
    usual, rc.WinterRelease = rc.WinterRelease, rules.LateForecastRelease
    try:
        perfect = rc.seasonal_forecast(inflows, 1.0)
        assert late.winter == rc.simulate_winter(inflows, rc.WinterPlan(70.0, 0.0), forecast=perfect).scores, "exercise 6 differs"
        row = lessons.table("late_1").query("winter_trigger == 72 and winter_ration == 0.5").iloc[0]
        assert abs(rc.simulate_winter(inflows, rc.WinterPlan(72.0, 0.5), forecast=perfect).scores.winter_shortage - row.winter_shortage) < 1e-5, "the stored table of exercise 6 differs"
    finally:
        rc.WinterRelease = usual
    assert late.winter != lessons.run(drawing("ex_late", forecast="1", late_forecast=False, winter_trigger=70, winter_ration=0.0)).winter
    for graph in (drawing("ex_seasonal", trigger=20, ration=0.8, ration_late=0.5), drawing("ex_late", forecast="0.8", late_forecast=True, winter_trigger=70, winter_ration=0.0), drawing("ex_cautious", forecast="0.8", caution=True, winter_trigger=70, winter_ration=0.0)):
        scope = {}
        exec(bc.to_python(graph), scope)
        assert same(rc._scores(rc.shortage_by_month(scope["system"])), lessons.run(graph).result.scores), "an exercise's shown code gives other numbers"

    # Hints: every unfinished drawing says what to do, every finished one is marked done
    for index, step in enumerate(lessons.STEPS):
        empty = lessons.evaluate({"nodes": [], "edges": []}, index, "en")
        assert not empty["done"] and empty["messages"], f"{step['key']}: no hint on an empty canvas"
        started = time.perf_counter()
        done = lessons.evaluate(lessons.solution(index), index, "en")
        assert done["done"] and done["figures"] and done["cards"] and done["code"], f"{step['key']}: solution not accepted: {done['messages']}"
        kb = sum(len(figure["svg"] if isinstance(figure, dict) else figure) for figure in done["figures"]) / 1024
        print(f"step {index + 1} {step['key']}: {len(done['figures'])} figure(s), {kb:.0f} KB, {time.perf_counter() - started:.2f} s")
        if index:  # the previous step's finished drawing is a valid start but not yet this step's goal
            before = lessons.evaluate(lessons.solution(index - 1), index, "en")
            assert not before["done"] and before["messages"], f"{step['key']}: done without doing anything"
    half = {"nodes": lessons.solution(0)["nodes"], "edges": [{"source": "river", "target": "farm"}]}
    assert "Farm" in lessons.evaluate(half, 0, "en")["messages"][0]["text"]
    assert "Winter fields" in lessons.evaluate(lessons.solution(STEP["winter"]), STEP["rationing"], "en")["messages"][0]["text"]

    # Every text the lesson asked for on the way exists
    lessons.lesson("en")
    lessons.lesson("en", "sandbox")
    assert not i18n.MISSING, f"texts without words: {sorted(i18n.MISSING)}"

    # Russian and Uzbek have every text, with the same blanks to fill
    import re

    for code in ("ru", "uz"):
        words = i18n.WORDS[code]
        assert set(words) == set(i18n.EN), (code, sorted(set(words) ^ set(i18n.EN)))
        for key, english in i18n.EN.items():
            assert sorted(re.findall(r"{[^}]*}", english)) == sorted(re.findall(r"{[^}]*}", words[key])), (code, key)
            assert bool(english) == bool(words[key]), (code, key)
        shown = lessons.evaluate(lessons.solution(STEP["winter"]), STEP["winter"], code)
        assert shown["done"] and "Mm³" not in shown["cards"][0]["value"] and "Mm³" not in str(lessons.lesson(code)["steps"][1]["fields"])

    # The widget answers a change and builds a step on request
    widget = BlockEditor()
    widget.step, widget.request = 1, "solve"
    assert widget.state["done"] and len(widget.graph["nodes"]) == 4
    widget.step, widget.request = len(lessons.STEPS) - 1, "solve"
    assert widget.state["done"] and len(widget.graph["nodes"]) == 5
    free = BlockEditor(lesson="sandbox")
    free.request = "solve"
    assert len(free.lesson["steps"]) == 1 and len(free.graph["nodes"]) == 7 and free.state["figures"]
    widget.lang = "ru"
    assert widget.lesson["ui"]["next"] == "Следующий шаг" and widget.state["messages"][0]["text"] == i18n.t("ru", "step.ex_late.done")
    print("all checks passed")


if __name__ == "__main__":
    main()
