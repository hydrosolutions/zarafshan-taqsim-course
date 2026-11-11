"""From a drawing to a TaqSim system.

A drawing ("graph") is plain data, as the canvas sends it:

    {"nodes": [{"id": "river", "kind": "Source", "x": 60, "y": 110, "params": {...}}, ...],
     "edges": [{"source": "river", "target": "farm"}, ...]}

`check` finds what is still missing, in words a learner can act on. `build` makes the validated `WaterSystem`.
`to_python` writes the same system as the Python a learner would type in the coding notebook.
"""

from __future__ import annotations

from dataclasses import dataclass

from taqsim import Demand, Edge, Sink, Source, Storage, TimeSeries, WaterSystem
from taqsim.node import NoLoss
from taqsim.time import Frequency

from zarafshan_taqsim import rationing_coursebook as rc
from zarafshan_taqsim.block_editor import rules

# What each kind of block may have on its two sides. None means "any number".
PORTS: dict[str, tuple[int | None, int | None]] = {
    # kind: (incoming edges allowed, outgoing edges allowed)
    "Source": (0, 1),
    "Storage": (None, 1),
    "Demand": (None, 1),
    "Sink": (None, 0),
}


@dataclass(frozen=True)
class Problem:
    """Something the drawing still needs. `key` names the message, `names` fills its blanks."""

    key: str
    names: tuple[str, ...] = ()


def _edges(graph: dict) -> list[tuple[str, str]]:
    return [(edge["source"], edge["target"]) for edge in graph.get("edges", [])]


def check(graph: dict) -> list[Problem]:
    """List what keeps the drawing from running, most basic problem first. An empty list means it can run."""
    nodes = {node["id"]: node for node in graph.get("nodes", [])}
    edges = _edges(graph)
    if not nodes:
        return [Problem("empty")]
    problems: list[Problem] = []
    kinds = {node["kind"] for node in nodes.values()}
    if "Source" not in kinds:
        problems.append(Problem("no_source"))
    if "Sink" not in kinds:
        problems.append(Problem("no_sink"))
    for node_id, node in nodes.items():
        incoming = [source for source, target in edges if target == node_id]
        outgoing = [target for source, target in edges if source == node_id]
        allowed_in, allowed_out = PORTS[node["kind"]]
        if allowed_out == 1 and not outgoing:
            problems.append(Problem("no_way_out", (node_id,)))
        if allowed_in != 0 and not incoming:
            problems.append(Problem("no_way_in", (node_id,)))
    return problems


def _clip(value, low: float, high: float) -> float:
    return min(max(float(value), low), high)


def has_winter_fields(graph: dict) -> bool:
    return any(node["id"] == "winter_fields" for node in graph.get("nodes", []))


def regime_of(graph: dict) -> rc.Regime:
    """The river the drawing's Source stands for: the course's summer-peak river unless set otherwise."""
    for node in graph.get("nodes", []):
        if node["kind"] == "Source":
            return rc.REGIMES.get(node.get("params", {}).get("regime", ""), rc.CENTRAL_ASIA_REGIME)
    return rc.CENTRAL_ASIA_REGIME


def skill_of(params: dict) -> float | None:
    """The skill of the forecast the reservoir's rule looks at, or None when it has no forecast."""
    choice = str(params.get("forecast", "none"))
    return None if choice == "none" else float(choice)


def _policy(params: dict, winter: bool, forecast: tuple[float, ...]):
    trigger = _clip(params.get("trigger", 0.0), 0.0, rc.CAPACITY_MM3)
    ration = _clip(params.get("ration", 1.0), 0.0, 1.0)
    if not winter:
        if params.get("seasonal"):  # exercise 4: a ration for early and one for late summer
            return rules.SeasonalRationing(trigger=trigger, ration=ration, ration_late=_clip(params.get("ration_late", 1.0), 0.0, 1.0))
        return rc.RationingRelease(trigger=trigger, ration=ration)
    release = rules.LateForecastRelease if params.get("late_forecast") else rc.WinterRelease  # exercise 6
    return release(
        trigger=trigger,
        ration=ration,
        winter_trigger=_clip(params.get("winter_trigger", 0.0), 0.0, rc.WINTER_TRIGGER_MAX_MM3),
        winter_ration=_clip(params.get("winter_ration", 1.0), 0.0, 1.0),
        forecast=forecast,
    )


def _loss(params: dict):
    share = float(params.get("evaporation", 0.0))
    return rc.SummerEvaporation(share=share) if share > 0.0 else NoLoss()


def configure_from(graph: dict) -> None:
    """Set the lesson's numbers (reservoir size, what the farm needs) from the blocks that carry them.

    The rationing rule reads the farm's need and the capacity from `rationing_coursebook`, so they are set there
    before a system is built, exactly as the coding notebook does with `configure(...)` in its first cell.
    """
    settings: dict[str, float] = {}
    for node in graph.get("nodes", []):
        params = node.get("params", {})
        if node["kind"] == "Storage":
            settings["capacity"] = float(params.get("capacity", 40.0))
            settings["start_storage"] = min(float(params.get("initial_storage", 20.0)), settings["capacity"])
        elif node["kind"] == "Demand" and node["id"] == "farm":
            settings["summer_need"] = float(params.get("summer_need", 45.0))
            settings["winter_need"] = float(params.get("winter_need", 5.0))
        elif node["kind"] == "Source":
            settings["seed"] = int(params.get("seed", 72))  # which hundred years of the river (exercise 3)
    settings.setdefault("seed", 72)
    settings.setdefault("capacity", 40.0)
    settings.setdefault("start_storage", min(20.0, settings["capacity"]))
    settings.setdefault("summer_need", 45.0)
    settings.setdefault("winter_need", 5.0)
    rc.configure(**settings)
    # TaqSim checks a rule's numbers against the rule's bounds, which were written for the standard reservoir:
    # a larger reservoir may have a higher trigger
    for rule in (rc.RationingRelease, rc.WinterRelease, rules.SeasonalRationing, rules.LateForecastRelease):
        rule.__bounds__ = {**rule.__bounds__, "trigger": (0.0, rc.CAPACITY_MM3)}


def build(graph: dict, inflows: tuple[float, ...], forecast: tuple[float, ...] = ()) -> WaterSystem:
    """Build and validate the TaqSim system the drawing describes.

    Args:
        graph: The drawing. Call `configure_from(graph)` first so that the lesson's numbers match it.
        inflows: Monthly river inflow in Mm³ for every Source.
        forecast: One forecast of the summer inflow per year, for a winter rule that looks at one.

    Returns:
        A validated system, not yet simulated.

    Raises:
        ValueError: If TaqSim finds the network invalid.
    """
    years = len(inflows) // 12
    winter = has_winter_fields(graph)
    system = WaterSystem(frequency=Frequency.MONTHLY)
    for node in graph["nodes"]:
        node_id, kind, params = node["id"], node["kind"], node.get("params", {})
        if kind == "Source":
            system.add_node(Source(id=node_id, inflow=TimeSeries(values=list(inflows))))
        elif kind == "Storage":
            system.add_node(
                Storage(
                    id=node_id,
                    capacity=rc.CAPACITY_MM3,
                    initial_storage=rc.START_STORAGE_MM3,
                    release_policy=_policy(params, winter, forecast),
                    loss_rule=_loss(params),
                )
            )
        elif kind == "Demand":
            need = rc.WINTER_FIELDS_NEED_MM3 if node_id == "winter_fields" else rc.MONTHLY_NEED_MM3
            system.add_node(Demand(id=node_id, requirement=TimeSeries(values=list(need) * years)))
        elif kind == "Sink":
            system.add_node(Sink(id=node_id))
        else:
            raise ValueError(f"unknown kind of block: {kind}")
    for source, target in _edges(graph):
        system.add_edge(Edge(id=f"{source}_to_{target}", source=source, target=target))
    system.validate()
    return system


def to_python(graph: dict) -> str:
    """The drawing as the Python of the coding notebook. Running it builds the same system."""
    winter, regime = has_winter_fields(graph), regime_of(graph)
    lines = [
        "from taqsim import Demand, Edge, Sink, Source, Storage, TimeSeries, WaterSystem",
        "from taqsim.node import NoLoss",
        "from taqsim.time import Frequency",
        "from zarafshan_taqsim.rationing_coursebook import MONTHLY_NEED_MM3, WINTER_FIELDS_NEED_MM3, YEARS, REGIMES",
        "from zarafshan_taqsim.rationing_coursebook import RationingRelease, SummerEvaporation, WinterRelease",
        "from zarafshan_taqsim.rationing_coursebook import configure, seasonal_forecast, synthetic_inflows",
        "from zarafshan_taqsim.block_editor.rules import LateForecastRelease, SeasonalRationing",
        "",
    ]
    settings = []
    for node in graph.get("nodes", []):
        params = node.get("params", {})
        if node["kind"] == "Storage":
            capacity = float(params.get("capacity", 40.0))
            start = min(float(params.get("initial_storage", 20.0)), capacity)
            settings += [f"capacity={capacity:g}", f"start_storage={start:g}"]
        elif node["kind"] == "Demand" and node["id"] == "farm":
            settings += [
                f"summer_need={float(params.get('summer_need', 45.0)):g}",
                f"winter_need={float(params.get('winter_need', 5.0)):g}",
            ]
        elif node["kind"] == "Source" and int(params.get("seed", 72)) != 72:
            settings.append(f"seed={int(params['seed'])}")
    lines += [
        f"configure({', '.join(settings)})  # the numbers of this model",
        f'inflows = synthetic_inflows(regime=REGIMES["{regime.name}"])  # 100 years of monthly river flow, Mm³',
        "",
        "system = WaterSystem(frequency=Frequency.MONTHLY)",
    ]
    for node in graph.get("nodes", []):
        node_id, kind, params = node["id"], node["kind"], node.get("params", {})
        if kind == "Source":
            lines.append(f'system.add_node(Source(id="{node_id}", inflow=TimeSeries(values=list(inflows))))')
        elif kind == "Storage":
            capacity = float(params.get("capacity", 40.0))
            start = min(float(params.get("initial_storage", 20.0)), capacity)
            trigger = min(float(params.get("trigger", 0.0)), capacity)
            share = float(params.get("evaporation", 0.0))
            loss = f"SummerEvaporation(share={share:g})" if share > 0.0 else "NoLoss()"
            rule = f"RationingRelease(trigger={trigger:g}, ration={float(params.get('ration', 1.0)):g})"
            if params.get("seasonal") and not winter:
                rule = f"SeasonalRationing(trigger={trigger:g}, ration={float(params.get('ration', 1.0)):g}, ration_late={float(params.get('ration_late', 1.0)):g})"
            if winter:
                skill = skill_of(params)
                forecast = "" if skill is None else f", forecast=seasonal_forecast(inflows, skill={skill:g})"
                if skill is not None and params.get("caution"):  # count only part of the forecast
                    forecast = f", forecast=tuple(0.7 * value for value in seasonal_forecast(inflows, skill={skill:g}))"
                rule = (
                    f"{'LateForecastRelease' if params.get('late_forecast') else 'WinterRelease'}(trigger={trigger:g}, ration={float(params.get('ration', 1.0)):g}, "
                    f"winter_trigger={float(params.get('winter_trigger', 0.0)):g}, "
                    f"winter_ration={float(params.get('winter_ration', 1.0)):g}{forecast})"
                )
            lines += [
                "system.add_node(",
                "    Storage(",
                f'        id="{node_id}",',
                f"        capacity={capacity:g},",
                f"        initial_storage={start:g},",
                f"        release_policy={rule},",
                f"        loss_rule={loss},",
                "    )",
                ")",
            ]
        elif kind == "Demand":
            need = "WINTER_FIELDS_NEED_MM3" if node_id == "winter_fields" else "MONTHLY_NEED_MM3"
            lines.append(f'system.add_node(Demand(id="{node_id}", requirement=TimeSeries(values=list({need}) * YEARS)))')
        elif kind == "Sink":
            lines.append(f'system.add_node(Sink(id="{node_id}"))')
    for source, target in _edges(graph):
        lines.append(f'system.add_edge(Edge(id="{source}_to_{target}", source="{source}", target="{target}"))')
    lines += ["", "system.validate()  # check the network", "system.simulate(len(inflows))  # run all 1,200 months"]
    return "\n".join(lines)
