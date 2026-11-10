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


def _policy(params: dict):
    capacity = rc.CAPACITY_MM3
    trigger = min(max(float(params.get("trigger", 0.0)), 0.0), capacity)
    ration = min(max(float(params.get("ration", 1.0)), 0.0), 1.0)
    return rc.RationingRelease(trigger=trigger, ration=ration)


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
    settings.setdefault("capacity", 40.0)
    settings.setdefault("start_storage", min(20.0, settings["capacity"]))
    settings.setdefault("summer_need", 45.0)
    settings.setdefault("winter_need", 5.0)
    rc.configure(**settings)


def build(graph: dict, inflows: tuple[float, ...]) -> WaterSystem:
    """Build and validate the TaqSim system the drawing describes.

    Args:
        graph: The drawing. Call `configure_from(graph)` first so that the lesson's numbers match it.
        inflows: Monthly river inflow in Mm³ for every Source.

    Returns:
        A validated system, not yet simulated.

    Raises:
        ValueError: If TaqSim finds the network invalid.
    """
    years = len(inflows) // 12
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
                    release_policy=_policy(params),
                    loss_rule=_loss(params),
                )
            )
        elif kind == "Demand":
            system.add_node(Demand(id=node_id, requirement=TimeSeries(values=list(rc.MONTHLY_NEED_MM3) * years)))
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
    lines = [
        "from taqsim import Demand, Edge, Sink, Source, Storage, TimeSeries, WaterSystem",
        "from taqsim.node import NoLoss",
        "from taqsim.time import Frequency",
        "from zarafshan_taqsim.rationing_coursebook import MONTHLY_NEED_MM3, YEARS, RationingRelease, SummerEvaporation",
        "from zarafshan_taqsim.rationing_coursebook import configure, synthetic_inflows",
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
    lines += [
        f"configure({', '.join(settings)})  # the numbers of this model",
        "inflows = synthetic_inflows()  # 100 years of monthly river flow, Mm³",
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
            lines += [
                "system.add_node(",
                "    Storage(",
                f'        id="{node_id}",',
                f"        capacity={capacity:g},",
                f"        initial_storage={start:g},",
                f"        release_policy=RationingRelease(trigger={trigger:g}, ration={float(params.get('ration', 1.0)):g}),",
                f"        loss_rule={loss},",
                "    )",
                ")",
            ]
        elif kind == "Demand":
            lines.append(
                f'system.add_node(Demand(id="{node_id}", requirement=TimeSeries(values=list(MONTHLY_NEED_MM3) * YEARS)))'
            )
        elif kind == "Sink":
            lines.append(f'system.add_node(Sink(id="{node_id}"))')
    for source, target in _edges(graph):
        lines.append(f'system.add_edge(Edge(id="{source}_to_{target}", source="{source}", target="{target}"))')
    lines += ["", "system.validate()  # check the network", "system.simulate(len(inflows))  # run all 1,200 months"]
    return "\n".join(lines)
