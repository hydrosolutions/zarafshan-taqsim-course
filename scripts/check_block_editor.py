"""Check that a drawing in the block editor gives the same numbers as the coding notebook.

Run it in an environment that has taqsim, anywidget and the builder wheel (or `src` on the path):

    python scripts/check_block_editor.py
"""

import time

from zarafshan_taqsim import rationing_coursebook as rc
from zarafshan_taqsim.block_editor import compile as bc
from zarafshan_taqsim.block_editor import lessons
from zarafshan_taqsim.block_editor.widget import BlockEditor


def same(a: rc.Scores, b: rc.Scores) -> bool:
    return abs(a.mean_shortage - b.mean_shortage) < 1e-9 and abs(a.worst_month - b.worst_month) < 1e-9 and a.years_short == b.years_short


def main() -> None:
    inflows = rc.synthetic_inflows()

    # Step 1: river → farm → outlet equals the notebook's run without a reservoir
    mine, spilled = lessons.run(lessons.solution(0))
    assert spilled is None and same(mine.scores, rc.simulate_without_reservoir(inflows).scores), "step 1 differs"

    # Step 2: with the reservoir, no rationing
    mine, spilled = lessons.run(lessons.solution(1))
    assert same(mine.scores, rc.simulate_plan(inflows, rc.NO_RATIONING).scores), "step 2 differs"
    assert spilled > 0

    # Step 3: the notebook's three plans and the learner's cell
    for trigger, ration in ((16, 0.8), (16, 0.5), (22, 0.55)):
        graph = lessons.solution(2)
        graph["nodes"][1]["params"].update(trigger=trigger, ration=ration)
        started = time.perf_counter()
        mine, _ = lessons.run(graph)
        seconds = time.perf_counter() - started
        theirs = rc.simulate_plan(inflows, rc.Plan(trigger, ration))
        assert same(mine.scores, theirs.scores) and (mine.storage == theirs.storage).all(), f"plan {trigger}, {ration} differs"
        print(f"plan trigger={trigger} ration={ration}: {mine.scores}  ({seconds:.2f} s)")

    # The code shown to the learner builds the same system
    graph = lessons.solution(2)
    scope: dict = {}
    exec(bc.to_python(graph), scope)
    shown = rc._scores(rc.shortage_by_month(scope["system"]))
    assert same(shown, lessons.run(graph)[0].scores), "the shown code gives other numbers"

    # Other sizes: a changed capacity and need reach the model
    graph = lessons.solution(1)
    graph["nodes"][1]["params"].update(capacity=80, initial_storage=100)
    graph["nodes"][2]["params"].update(summer_need=60)
    big, _ = lessons.run(graph)
    assert rc.CAPACITY_MM3 == 80 and rc.START_STORAGE_MM3 == 80 and rc.SUMMER_NEED_MM3 == 60
    rc.configure(capacity=40, start_storage=20, summer_need=45, winter_need=5)

    # Hints: every unfinished drawing says what to do, every finished one is marked done
    for step in range(len(lessons.STEPS)):
        empty = lessons.evaluate({"nodes": [], "edges": []}, step, "en")
        assert not empty["done"] and empty["messages"], f"step {step + 1}: no hint on an empty canvas"
        done = lessons.evaluate(lessons.solution(step), step, "en")
        assert done["done"] and done["figures"] and done["cards"] and done["code"], f"step {step + 1}: solution not accepted"
    half = {"nodes": lessons.solution(0)["nodes"], "edges": [{"source": "river", "target": "farm"}]}
    assert "Farm" in lessons.evaluate(half, 0, "en")["messages"][0]["text"]

    # The widget answers a change and builds a step on request
    widget = BlockEditor()
    widget.step, widget.request = 1, "solve"
    assert widget.state["done"] and len(widget.graph["nodes"]) == 4
    print(f"figure: {len(widget.state['figures'][0]) / 1024:.0f} KB of SVG")
    print("all checks passed")


if __name__ == "__main__":
    main()
