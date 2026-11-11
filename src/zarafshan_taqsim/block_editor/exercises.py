"""The six exercises at the end of the rationing coursebook, as steps of the block editor.

Each exercise keeps the lesson's model and changes one thing: the size of the reservoir, the second goal, the
river, the rule (two rations), how much of the forecast the rule counts, and when the forecast arrives. One
run is live, as in the lesson; the comparison tables come from `precomputed.json`.

This module is imported at the end of `lessons.py`, whose helpers it uses.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from zarafshan_taqsim import rationing_coursebook as rc
from zarafshan_taqsim.block_editor import compile as bc
from zarafshan_taqsim.block_editor import lessons as L
from zarafshan_taqsim.block_editor.i18n import t

CAPACITIES = (40, 60, 80)
SKILLS = (0.3, 0.5, 0.65, 0.8, 0.9, 1.0)

_CAPACITY = [{"key": "capacity", "type": "choice", "options": [str(c) for c in CAPACITIES], "group": "size"}]
_GOAL = [{"key": "second_goal", "type": "choice", "options": ["worst_month", "years_short"], "group": "goal"}]
_SEED = [{"key": "seed", "type": "choice", "options": ["72", "1"]}]
_TWO_RATIONS = [
    L._RULE[0],
    {**L._RULE[1], "label_key": "field.ration_early"},
    {"key": "ration_late", "min": 0, "max": 1, "step": 0.05, "percent": True, "group": "rule"},
]
_CAUTION = [{"key": "caution", "type": "toggle", "group": "winter"}]
_LATE = [{"key": "late_forecast", "type": "toggle", "group": "winter"}]

_SIZE, _FARM, _OFF = L._STANDARD_SIZE, L._STANDARD_FARM, L._NOT_YET
_WINTER_LOCKS = {**_SIZE, **L._CUT_DEEP, "optimise": False, "evaporation": 0.0}
_WINTER_FIELDS = L._FORECAST + L._WINTER_FAR


def _step(key: str, fields: dict, reservoir: dict, river: dict | None = None, five: bool = False) -> dict:
    return {
        "key": key,
        "focus": "reservoir",
        "palette": L._FIVE if five else L._FOUR,
        "target": L.CHAIN_5 if five else L.CHAIN_4,
        "fields": {"farm": L._FARM, **fields},
        "locks": {"river": dict(L._OUR_RIVER) if river is None else river, "reservoir": reservoir, "farm": _FARM},
    }


# A lock of None means: free in this step (see the end of lessons.py)
STEPS: list[dict] = [
    _step("ex_capacity", {"reservoir": L._RULE + _CAPACITY}, {**_OFF, "initial_storage": 20, "capacity": None}),
    _step("ex_goal", {"reservoir": L._RULE + _GOAL + L._SIZE_SHOWN}, {**_OFF, **_SIZE, "second_goal": None}),
    {**_step("ex_river", {"river": L._REGIME + _SEED, "reservoir": L._RULE + L._SIZE_SHOWN}, {**_OFF, **_SIZE}, river={"seed": None}), "focus": "river"},
    _step("ex_seasonal", {"reservoir": _TWO_RATIONS + L._SIZE_SHOWN}, {**_OFF, **_SIZE, "seasonal": True, "ration_late": None}),
    _step("ex_cautious", {"reservoir": _WINTER_FIELDS + _CAUTION + L._RULE + L._SIZE_SHOWN}, {**_WINTER_LOCKS, "caution": None}, five=True),
    _step("ex_late", {"reservoir": _WINTER_FIELDS + _LATE + L._RULE + L._SIZE_SHOWN}, {**_WINTER_LOCKS, "late_forecast": None}, five=True),
]


def solve(key: str, params: dict) -> None:
    """Put in place the setting an exercise asks the learner to try (for "Build it for me")."""
    if not key.startswith("ex_"):
        return
    reservoir = params["reservoir"]
    if key == "ex_capacity":
        reservoir.update(capacity="60", trigger=20, ration=0.55)
    elif key == "ex_goal":
        reservoir.update(second_goal="years_short")
    elif key == "ex_river":
        params["river"].update(seed="1")
    elif key == "ex_seasonal":
        reservoir.update(trigger=20, ration=0.8, ration_late=0.5)
    elif key == "ex_cautious":
        reservoir.update(forecast="0.5", caution=True, winter_trigger=70, winter_ration=0.0)
    elif key == "ex_late":
        reservoir.update(forecast="1", late_forecast=True, winter_trigger=70, winter_ration=0.0)


# --- Figures ------------------------------------------------------------------------------------------------


@rc._styled
def plot_fronts(fronts: dict[str, pd.DataFrame], y: str = "worst_month", ylabel: str = "Worst month (% of its need not delivered)"):
    """The unbeaten plans of several score tables on one chart (up to five curves)."""
    fig, ax = plt.subplots(figsize=(7.4, 4.0))
    for (label, table), color in zip(fronts.items(), rc._FRONT_COLORS, strict=False):
        front = _front(table, y)
        front = front[front["mean_shortage"] <= rc.MEAN_SHORTAGE_AXIS_MAX]
        ax.plot(front["mean_shortage"], front[y], color=color, linewidth=1.6, drawstyle="steps-post", marker="o", markersize=5, markeredgecolor=rc.SURFACE, label=label)
    ax.set_xlabel("Average shortage (Mm³ per year)")
    ax.set_ylabel(ylabel)
    ax.set_xlim(0, rc.MEAN_SHORTAGE_AXIS_MAX)
    ax.set_ylim(0, 100)
    rc._better_arrows(ax)
    ax.legend(loc="upper right")
    rc._style(ax)
    fig.tight_layout()
    return fig


def _front(table: pd.DataFrame, y: str = "worst_month") -> pd.DataFrame:
    """The distinct unbeaten (average shortage, `y`) pairs of a score table, smallest shortage first."""
    if y == "worst_month":
        return rc.front_of(table)
    keep = rc.unbeaten(table[["mean_shortage", y]].to_numpy().round(6))
    front = table[keep].sort_values(["ration", "trigger"], ascending=[False, True])
    return front.round({"mean_shortage": 6, y: 6}).drop_duplicates(["mean_shortage", y]).sort_values("mean_shortage").reset_index(drop=True)


@rc._styled
def plot_years_tradeoff(table: pd.DataFrame, found: pd.DataFrame):
    """Every plan as a dot, with "years with a shortage" as the second goal instead of the worst month."""
    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    front = _front(table, "years_short")
    ax.scatter(table["mean_shortage"], table["years_short"], s=13, color=rc.REFERENCE, linewidths=0, label="beaten plan")
    ax.plot(front["mean_shortage"], front["years_short"], color=rc.INK, linewidth=1.0, drawstyle="steps-post", zorder=2)
    ax.scatter(front["mean_shortage"], front["years_short"], s=34, color=rc.INK, edgecolors=rc.SURFACE, linewidths=1.2, zorder=3, label="unbeaten plan (grid)")
    ax.scatter(found["mean_shortage"], found["years_short"], s=30, color=rc.WATER, edgecolors=rc.SURFACE, linewidths=1.0, zorder=4, label="found by the optimizer")
    ax.set_xlabel("Average shortage (Mm³ per year)")
    ax.set_ylabel("Years with a shortage (of 100)")
    ax.set_xlim(0, rc.MEAN_SHORTAGE_AXIS_MAX)
    ax.set_ylim(0, 100)
    ax.text(0.01, 0.02, "better: further left (less water missed) and further down (fewer years short)", transform=ax.transAxes, fontsize=8, color=rc.MUTED, ha="left", va="bottom")
    ax.legend(loc="upper right")
    rc._style(ax)
    fig.tight_layout()
    return fig


@rc._styled
def plot_forecast_pairs(first: dict[str, float], second: dict[str, float], labels: tuple[str, str], none: tuple[str, float], cap: float):
    """Two bars for each quality of forecast (one rule beside the other), and the level without a forecast."""
    fig, ax = plt.subplots(figsize=(7.4, 3.7))
    names, at = list(first), np.arange(len(first))
    for shift, values, color, label in ((-0.2, first, rc.WATER, labels[0]), (0.2, second, L.YOURS, labels[1])):
        bars = ax.bar(at + shift, list(values.values()), width=0.38, color=color, label=label)
        for bar, value in zip(bars, values.values(), strict=True):
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.1, f"{value:.1f}", ha="center", fontsize=8.5, color=rc.INK)
    ax.axhline(none[1], color=rc.MUTED, linewidth=1.2, linestyle=(0, (4, 3)))
    ax.text(len(names) - 0.52, none[1] + 0.12, f"{none[0]}: {none[1]:.1f}", ha="right", fontsize=8.5, color=rc.MUTED)
    ax.set_xticks(at, names)
    ax.set_title(f"What the winter fields give up when the farm misses at most {cap:g} Mm³ a year", loc="left")
    ax.set_ylabel("Winter fields: water missed\n(Mm³ per year)")
    ax.set_xlabel("Quality of the forecast (skill: 0 = knows nothing, 1 = perfect)")
    ax.set_ylim(0, max(*first.values(), *second.values(), none[1]) * 1.3)
    ax.legend(loc="upper right", ncol=2)
    rc._style(ax)
    fig.tight_layout()
    return fig


# --- What each exercise shows -------------------------------------------------------------------------------


def _story_and_verdict(lang: str, mine: L.Run, in_full: rc.RunResult, grid: pd.DataFrame) -> str:
    scores = mine.result.scores
    beaten = L.beaten_by(scores.mean_shortage, scores.worst_month, grid)
    verdict = t(lang, "note.unbeaten") if beaten == 0 else t(lang, "note.beaten", n=beaten)
    return L._plan_story(lang, mine, in_full) + " " + verdict


def _show_capacity(state: dict, mine: L.Run, lang: str, graph: dict) -> str | None:
    capacity = int(rc.CAPACITY_MM3)
    name = lambda c: "grid" if c == 40 else f"grid_capacity_{c}"  # noqa: E731
    grid, key = L.table(name(capacity)), L._settings_key()
    in_full, without = L._reference("full", key, rc.CENTRAL_ASIA_REGIME), L._reference("none", key, rc.CENTRAL_ASIA_REGIME)
    sizes = {t(lang, "label.capacity", capacity=c): L.table(name(c)) for c in CAPACITIES}
    fronts = plot_fronts(sizes)
    points = [point for label, plans in sizes.items() for point in L._plan_points(lang, rc.front_of(plans), label)]
    first = {c: rc.front_of(L.table(name(c))).iloc[0] for c in CAPACITIES}  # the plan that misses least: no rationing
    numbers = {f"{letter}{c}": getattr(first[c], column) for c in CAPACITIES for letter, column in (("m", "mean_shortage"), ("w", "worst_month"))}
    state["figures"] = [
        L._figure(L._tradeoff(lang, mine.result, in_full, grid=grid, without=without), t(lang, "caption.ex_capacity_plans", capacity=capacity)),
        L._figure(L._svg(fronts, L._tips(fronts, points)), t(lang, "caption.ex_capacity_fronts", **numbers)),
    ]
    state["cards"] = L._goal_cards(lang, mine, in_full)
    state["note"] = _story_and_verdict(lang, mine, in_full, grid)
    return None if capacity != 40 else "hint.ex_capacity"


def _show_goal(state: dict, mine: L.Run, lang: str, graph: dict) -> str | None:
    key, grid = L._settings_key(), L.table("grid")
    in_full, without = L._reference("full", key, rc.CENTRAL_ASIA_REGIME), L._reference("none", key, rc.CENTRAL_ASIA_REGIME)
    if mine.params.get("second_goal") != "years_short":
        state["cards"] = L._goal_cards(lang, mine, in_full)
        state["figures"] = [L._figure(L._tradeoff(lang, mine.result, in_full, found=L.table("found"), without=without), t(lang, "caption.ex_goal_before"))]
        return "hint.ex_goal"
    found = L.table("found_years")
    fig = plot_years_tradeoff(grid, found)
    front = _front(grid, "years_short")
    for run, label, colour, offset in ((in_full, "label.in_full", L.IN_FULL, (10, 12)), (mine.result, "label.yours", L.YOURS, (12, -16))):
        L._mark(fig, run.scores.mean_shortage, run.scores.years_short, t(lang, label), colour, offset)
    points = [
        (row.mean_shortage, row.years_short, t(lang, "tip.plan_years", trigger=row.trigger, ration=row.ration * 100, missed=row.mean_shortage, years=row.years_short))
        for frame in (front, found)
        for row in frame.itertuples()
    ]
    full = in_full.scores
    still = not ((grid["mean_shortage"] <= full.mean_shortage + 1e-6) & (grid["years_short"] <= full.years_short) & ((grid["mean_shortage"] < full.mean_shortage - 1e-6) | (grid["years_short"] < full.years_short))).any()
    caption = t(lang, "caption.ex_goal", n=len(front), still=t(lang, "word.still" if still else "word.no_longer"))
    state["figures"] = [L._figure(L._svg(fig, L._tips(fig, points)), caption)]
    state["cards"] = L._goal_cards(lang, mine, in_full, second="years_short")
    state["note"] = L._plan_story(lang, mine, in_full)
    return None


def _show_river(state: dict, mine: L.Run, lang: str, graph: dict) -> str | None:
    regime, seed, key = bc.regime_of(graph), int(rc.SEED), L._settings_key()
    name = lambda paper, other: ("paper_grid" if paper else "grid") + ("_seed_1" if other else "")  # noqa: E731
    river = lambda paper, other: f"{t(lang, 'system.winter' if paper else 'system.summer')}, {t(lang, 'option.seed.1' if other else 'option.seed.72')}"  # noqa: E731
    paper, other = regime.name == "paper", seed != 72
    grid = L.table(name(paper, other))
    in_full, without = L._reference("full", key, regime), L._reference("none", key, regime)
    rivers = {river(p, o): L.table(name(p, o)) for o in (False, True) for p in (False, True)}
    fronts = plot_fronts(rivers)
    points = [point for label, plans in rivers.items() for point in L._plan_points(lang, rc.front_of(plans), label)]
    state["figures"] = [
        L._figure(L._tradeoff(lang, mine.result, in_full, grid=grid, without=without), t(lang, "caption.ex_river_plans", river=river(paper, other))),
        L._figure(L._svg(fronts, L._tips(fronts, points)), t(lang, "caption.ex_river_fronts")),
    ]
    state["cards"] = L._goal_cards(lang, mine, in_full)
    state["note"] = _story_and_verdict(lang, mine, in_full, grid)
    return None if other else "hint.ex_river"


def _least_shortage(plans: pd.DataFrame, worst_month: float) -> float:
    within = plans[plans["worst_month"] <= worst_month + 1e-6]
    return float(within["mean_shortage"].min()) if len(within) else float("nan")


def _show_seasonal(state: dict, mine: L.Run, lang: str, graph: dict) -> str | None:
    key, grid, found = L._settings_key(), L.table("grid"), L.table("found_seasonal")
    in_full, without = L._reference("full", key, rc.CENTRAL_ASIA_REGIME), L._reference("none", key, rc.CENTRAL_ASIA_REGIME)
    one = pd.concat([grid, L.table("found")])  # every plan with one ration that was tried
    beats = sum(L.beaten_by(row.mean_shortage, row.worst_month, one) == 0 and (row.mean_shortage, row.worst_month) not in set(zip(one["mean_shortage"], one["worst_month"], strict=True)) for row in found.itertuples())
    goal = L.WORST_MONTH_GOAL
    caption = t(lang, "caption.ex_seasonal", n=beats, total=len(found), goal=goal, one=_least_shortage(one, goal), two=_least_shortage(found, goal))
    early, late = float(mine.params.get("ration", 1.0)), float(mine.params.get("ration_late", 1.0))
    label = f"{t(lang, 'label.yours')}: {t(lang, 'label.plan_seasonal', trigger=mine.result.plan.trigger, ration=early * 100, late=late * 100)}"
    runs = {t(lang, "label.in_full"): in_full, label: mine.result}
    state["figures"] = [
        L._figure(L._tradeoff(lang, mine.result, in_full, found=found, without=without, found_tip="tip.seasonal"), caption),
        L._figure(L._runs_svg(lang, rc.plot_runs(runs, first_year=rc.drought_window_start(in_full)), runs), t(lang, "caption.plan_run")),
    ]
    state["cards"] = L._goal_cards(lang, mine, in_full)
    scores = mine.result.scores
    beaten = L.beaten_by(scores.mean_shortage, scores.worst_month, grid)
    state["note"] = t(lang, "note.unbeaten_one_ration") if beaten == 0 else t(lang, "note.beaten_one_ration", n=beaten)
    return None if float(mine.params.get("trigger", 0)) > 0 and late < 1.0 and abs(early - late) > 1e-9 else "hint.ex_seasonal"


def _show_variant(state: dict, mine: L.Run, lang: str, graph: dict, kind: str) -> str | None:
    """Exercises 5 and 6: the winter rule with a forecast, used in full or in the exercise's way."""
    flag = {"cautious": "caution", "late": "late_forecast"}[kind]
    skill, on = bc.skill_of(mine.params), bool(mine.params.get(flag))
    scores, full = mine.winter, L._reference("winter_in_full", L._settings_key(), rc.CENTRAL_ASIA_REGIME).scores
    name = t(lang, "label.winter_in_full")
    state["cards"] = [
        L._card(lang, "summer_shortage", f"{scores.summer_shortage:.1f} Mm³", f"{full.summer_shortage:.1f}", name),
        L._card(lang, "winter_shortage", f"{scores.winter_shortage:.1f} Mm³", f"{full.winter_shortage:.1f}", name),
        L._card(lang, "worst_month", f"{scores.worst_month:.0f} %", f"{full.worst_month:.0f} %", name),
    ]
    plain, changed = t(lang, f"label.{kind}_off"), t(lang, f"label.{kind}_on")
    shown = skill if skill is not None else 0.5
    curves = {
        f"{plain} ({shown:g})": L.table(f"skill_{shown:g}"),
        f"{changed} ({shown:g})": L.table(f"{kind}_{shown:g}"),
        t(lang, "label.storage_alone"): L.table("storage_only"),
    }
    fronts = L._mark(rc.plot_winter_fronts(curves), scores.summer_shortage, scores.winter_shortage, t(lang, "label.yours"))
    points = [
        (row.summer_shortage, row.winter_shortage, f"{label}: " + t(lang, "tip.winter_plan", trigger=row.winter_trigger, ration=row.winter_ration * 100, summer=row.summer_shortage, winter=row.winter_shortage))
        for label, frame in curves.items()
        for row in rc.winter_front_of(frame).itertuples()
    ]
    cap = L.SUMMER_CAP
    loss = lambda prefix: {L._SKILL_NAMES[s]: rc.least_winter_shortage(L.table(f"{prefix}_{s:g}"), cap) for s in SKILLS}  # noqa: E731
    first, second = loss("skill"), loss(kind)
    none = rc.least_winter_shortage(L.table("storage_only"), cap)
    bars = plot_forecast_pairs(first, second, (plain, changed), (t(lang, "label.no_forecast"), none), cap)
    weak, strong = L._SKILL_NAMES[0.5], L._SKILL_NAMES[1.0]
    gain = none - second[strong]  # what the exercise's rule saves the winter fields with a perfect forecast
    numbers = {"cap": cap, "full_weak": first[weak], "var_weak": second[weak], "full_strong": first[strong], "var_strong": second[strong], "early_gain": none - first[strong]}
    if kind == "late":  # with one trigger for the whole winter, a late forecast can do worse than none: say what the numbers say
        numbers["late"] = t(lang, "caption.ex_late_part", late_gain=gain) if gain > 0.05 else t(lang, "caption.ex_late_worse", late_loss=-gain)
    state["figures"] = [
        L._figure(L._svg(fronts, L._tips(fronts, points)), t(lang, "caption.ex_variant_fronts", skill=shown)),
        L._figure(bars, t(lang, f"caption.ex_{kind}_bars", **numbers)),
    ]
    state["note"] = t(lang, "note.forecast_off") if skill is None else t(lang, f"note.ex_{kind}_{'on' if on else 'off'}", skill=skill)
    return None if skill is not None and on else f"hint.ex_{kind}"


SHOW = {
    "ex_capacity": _show_capacity,
    "ex_goal": _show_goal,
    "ex_river": _show_river,
    "ex_seasonal": _show_seasonal,
    "ex_cautious": lambda state, mine, lang, graph: _show_variant(state, mine, lang, graph, "cautious"),
    "ex_late": lambda state, mine, lang, graph: _show_variant(state, mine, lang, graph, "late"),
}
