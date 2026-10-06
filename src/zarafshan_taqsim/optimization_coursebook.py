"""Lean helper functions for the optimization coursebook.

The functions in this module keep the Quarto document focused on teaching
flow. They wrap demonstration simulations, small summary tables, and repeated
plotting patterns used only by the optimization coursebook.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from taqsim import Reach, WaterSystem
from taqsim.node.events import DeficitRecorded, WaterReceived, WaterReleased, WaterSpilled
from taqsim.time import Timestep

from zarafshan_taqsim.cache import OptimizationConfig, run_or_load
from zarafshan_taqsim.convergence import ConvergenceHistory, make_convergence_callback
from zarafshan_taqsim.data import DEFAULT_DISTRICTS
from zarafshan_taqsim.network import (
    NODE_COLORS,
    NODE_SIZES,
    _get_geographic_positions,
    apply_static_demand_splitting,
    create_zrb_system,
)
from zarafshan_taqsim.optimize_runner import run_optimization
from zarafshan_taqsim.strategies import MonthlyDistribution, ZRBReleaseRule

MM3 = 1e6
_SERIES_COLORS = ("#3b82f6", "#10b981", "#ef4444", "#8b5cf6", "#f59e0b")


@dataclass(frozen=True)
class PolicyVariant:
    """Compact result for a manual policy experiment."""

    label: str
    storage: list[float] | None = None
    karmana_flow: list[float] | None = None
    deficit: float | None = None
    spillage: float | None = None
    deficits: dict[str, float] | None = None


def plot_pareto_idea(seed: int = 42) -> plt.Figure:
    """Create the introductory two-objective Pareto-front sketch."""
    rng = np.random.default_rng(seed)

    x_dom = rng.uniform(1.5, 8.0, 80)
    y_dom = rng.uniform(1.5, 8.0, 80)
    y_front_at_x = 0.5 + 6.0 * np.exp(-0.5 * x_dom)
    above_front = y_dom > y_front_at_x + 0.3
    x_dom = x_dom[above_front]
    y_dom = y_dom[above_front]

    x_front = np.linspace(0.5, 7.0, 20)
    y_front = 0.5 + 6.0 * np.exp(-0.5 * x_front)
    y_front += rng.normal(0, 0.1, len(x_front))
    y_front = np.maximum(y_front, 0.3)

    fig, ax = plt.subplots(figsize=(7, 5))
    x_fill = np.concatenate([[0], x_front, [8]])
    y_fill = np.concatenate([[y_front[0]], y_front, [0]])
    ax.fill_between(x_fill, y_fill, 0, alpha=0.08, color="blue", label="Infeasible region")

    ax.scatter(x_dom, y_dom, c="grey", alpha=0.4, s=30, label="Dominated solutions", zorder=2)
    ax.scatter(x_front, y_front, c="#2563eb", s=50, zorder=3, label="Pareto front")
    ax.plot(x_front, y_front, c="#2563eb", alpha=0.5, linewidth=1.5, zorder=2)

    ax.set_xlabel("Objective 1: Total Agricultural Deficit (Mm3)", fontsize=11)
    ax.set_ylabel("Objective 2: Reservoir Spillage (Mm3)", fontsize=11)
    ax.set_xlim(0, 8.5)
    ax.set_ylim(0, 9)
    ax.legend(loc="upper right", fontsize=9)
    ax.set_title("The Pareto Front: Best-Possible Tradeoffs", fontsize=12)
    ax.annotate(
        "Less deficit, more spillage",
        xy=(1.0, 4.5),
        xytext=(2.5, 6.5),
        fontsize=9,
        color="#2563eb",
        style="italic",
        arrowprops={"arrowstyle": "->", "color": "#2563eb"},
    )
    ax.annotate(
        "Less spillage, more deficit",
        xy=(5.5, 0.7),
        xytext=(4.0, 2.5),
        fontsize=9,
        color="#2563eb",
        style="italic",
        arrowprops={"arrowstyle": "->", "color": "#2563eb"},
    )
    plt.tight_layout()
    return fig


def plot_pareto_concept() -> plt.Figure:
    """Create formal Pareto-front sketch with hypervolume and knee point."""
    fig, ax = plt.subplots(figsize=(7, 5))
    x_f = np.linspace(0.5, 7, 30)
    y_f = 0.5 + 5.5 * np.exp(-0.45 * x_f)
    ref_x, ref_y = 8.5, 7.5

    for i in range(len(x_f) - 1):
        ax.fill(
            [x_f[i], x_f[i + 1], x_f[i + 1], x_f[i]],
            [y_f[i], y_f[i + 1], ref_y, ref_y],
            color="#dbeafe",
            alpha=0.6,
            linewidth=0,
        )
    ax.fill([x_f[-1], ref_x, ref_x, x_f[-1]], [y_f[-1], y_f[-1], ref_y, ref_y], color="#dbeafe", alpha=0.6, linewidth=0)

    ax.plot(x_f, y_f, "o-", color="#2563eb", markersize=4, linewidth=1.5, label="Pareto front")
    knee_idx = 8
    ax.plot(x_f[knee_idx], y_f[knee_idx], "s", color="#f59e0b", markersize=12, zorder=5, label="Knee point")
    ax.plot(ref_x, ref_y, "D", color="#dc2626", markersize=10, zorder=5, label="Reference point")
    ax.annotate("Hypervolume\n(shaded area)", xy=(6, 5), fontsize=9, color="#2563eb", ha="center", style="italic")
    ax.annotate("Dominated region\n(above/right of front)", xy=(5, 3), fontsize=8, color="grey", ha="center")

    ax.set_xlabel("Objective 1", fontsize=11)
    ax.set_ylabel("Objective 2", fontsize=11)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 8.5)
    ax.legend(fontsize=9)
    ax.set_title("Pareto Front, Hypervolume, and Knee Point", fontsize=12)
    plt.tight_layout()
    return fig


def baseline_district_summary(
    system: WaterSystem,
    timesteps: int,
    districts: list[str] | None = None,
) -> pd.DataFrame:
    """Summarize demand, deficit, and satisfaction by irrigation district."""
    rows = []
    frequency = getattr(system, "frequency", None)
    for district in districts or list(DEFAULT_DISTRICTS):
        node = system.nodes[district]
        total_demand = sum(node.requirement[Timestep(t, frequency=frequency)] for t in range(timesteps))
        deficit = node.trace(DeficitRecorded, field="deficit").sum()
        satisfaction = 1.0 - (deficit / total_demand) if total_demand > 0 else 1.0
        rows.append(
            {
                "District": district,
                "Total Demand (Mm3)": f"{total_demand / MM3:,.0f}",
                "Deficit (Mm3)": f"{deficit / MM3:,.0f}",
                "Satisfaction (%)": f"{satisfaction * 100:.1f}",
            }
        )
    return pd.DataFrame(rows)


def objective_catalog_table() -> pd.DataFrame:
    """Return the coursebook's candidate-objective catalog."""
    return pd.DataFrame(
        [
            {
                "ID": "O1",
                "Name": "Total agricultural deficit",
                "Direction": "minimise",
                "Implemented": "Yes",
                "Selected": "**Yes**",
            },
            {
                "ID": "O2",
                "Name": "Downstream env. flow deficit",
                "Direction": "minimise",
                "Implemented": "No",
                "Selected": "No",
            },
            {
                "ID": "O3",
                "Name": "Reservoir spillage",
                "Direction": "minimise",
                "Implemented": "No",
                "Selected": "No",
            },
            {
                "ID": "O4",
                "Name": "Power plant cooling deficit",
                "Direction": "minimise",
                "Implemented": "Yes",
                "Selected": "**Yes**",
            },
            {
                "ID": "O5",
                "Name": "Inter-basin transfer deficits",
                "Direction": "minimise",
                "Implemented": "No",
                "Selected": "No",
            },
            {
                "ID": "O6",
                "Name": "Equity (max district deficit)",
                "Direction": "minimise",
                "Implemented": "Yes",
                "Selected": "**Yes**",
            },
            {
                "ID": "O7",
                "Name": "Temporal deficit concentration",
                "Direction": "minimise",
                "Implemented": "No",
                "Selected": "No",
            },
            {
                "ID": "O8",
                "Name": "Storage sustainability",
                "Direction": "minimise",
                "Implemented": "No",
                "Selected": "No",
            },
            {
                "ID": "O9",
                "Name": "Release variability",
                "Direction": "minimise",
                "Implemented": "Yes",
                "Selected": "**Yes**",
            },
        ]
    )


def baseline_objective_table(
    baseline_scores: dict[str, float],
    obj_names: list[str],
) -> pd.DataFrame:
    """Format baseline objective scores for notebook display."""
    return pd.DataFrame(
        [
            {
                "Objective": name,
                "Baseline Value (Mm3)": f"{baseline_scores[name] / MM3:,.1f}",
            }
            for name in obj_names
        ]
    )


def parameter_schema_summary(system: WaterSystem) -> pd.DataFrame:
    """Summarize ``WaterSystem.param_schema()`` by component and parameter."""
    rows = []
    for spec in system.param_schema():
        path = str(spec.path)
        component = path.split(".")[0]
        leaf = path.split(".")[-1]
        parameter = leaf.split("[")[0]
        rows.append({"Component": component, "Parameter": parameter, "Free values": 1})

    return pd.DataFrame(rows).groupby(["Component", "Parameter"], as_index=False)["Free values"].sum()


def decision_table_from_schema(schema_summary: pd.DataFrame) -> pd.DataFrame:
    """Add declared bounds to a parameter schema summary."""
    bounds_by_parameter = {
        "eflow_fraction": "[0, 1]",
        "vr": "[0, 500] m3/s",
        "v1": "[0, 1e9] m3",
        "v2": "[0, 1e9] m3",
        "buffer_coef": "[0, 1]",
        "flood_coef": "[0, 5]",
    }
    out = schema_summary.copy()
    out["Bounds"] = out["Parameter"].map(bounds_by_parameter)
    return out


def plot_tunable_parameter_map(
    system: WaterSystem,
    schema_summary: pd.DataFrame,
) -> plt.Figure:
    """Plot the geographic network with tunable component counts."""
    tunable_counts = schema_summary.groupby("Component")["Free values"].sum().to_dict()

    graph = nx.DiGraph()
    hidden_reaches: set[str] = set()
    for node_id, node in system.nodes.items():
        if isinstance(node, Reach):
            hidden_reaches.add(node_id)
            continue
        graph.add_node(node_id)

    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in system.edges.values():
        outgoing[edge.source].append(edge.target)

    collapsed_edges: set[tuple[str, str]] = set()
    for source in graph.nodes:
        stack = list(outgoing.get(source, []))
        seen_hidden: set[str] = set()
        while stack:
            target = stack.pop()
            if target in hidden_reaches:
                if target in seen_hidden:
                    continue
                seen_hidden.add(target)
                stack.extend(outgoing.get(target, []))
                continue
            if target in graph.nodes and source != target:
                collapsed_edges.add((source, target))

    for source, target in collapsed_edges:
        graph.add_edge(source, target)

    pos = _get_geographic_positions(system)
    pos = {node_id: coords for node_id, coords in pos.items() if node_id in graph.nodes}
    for node_id in graph.nodes:
        if node_id not in pos:
            pos[node_id] = (250000, 4420000)

    node_colors = []
    node_sizes = []
    for node_id in graph.nodes:
        node = system.nodes[node_id]
        if node_id in tunable_counts:
            node_colors.append(NODE_COLORS.get(type(node), "#95a5a6"))
            node_sizes.append(NODE_SIZES.get(type(node), 500))
        else:
            node_colors.append("#d5d8dc")
            node_sizes.append(400)

    fig, ax = plt.subplots(figsize=(14, 10))
    nx.draw_networkx_edges(
        graph,
        pos,
        ax=ax,
        edge_color="#bdc3c7",
        arrows=True,
        arrowsize=12,
        arrowstyle="-|>",
        connectionstyle="arc3,rad=0.05",
        width=1.2,
        alpha=0.6,
    )
    nx.draw_networkx_nodes(
        graph,
        pos,
        ax=ax,
        node_color=node_colors,
        node_size=node_sizes,
        alpha=0.9,
        edgecolors="white",
        linewidths=2,
    )
    nx.draw_networkx_labels(graph, pos, _short_labels(graph.nodes), ax=ax, font_size=7, font_weight="bold")

    for node_id, n_free in tunable_counts.items():
        if node_id not in pos:
            continue
        x, y = pos[node_id]
        ax.annotate(
            f"{n_free}",
            xy=(x, y),
            fontsize=14,
            fontweight="bold",
            color="#dc2626",
            ha="center",
            va="bottom",
            xytext=(0, 18),
            textcoords="offset points",
            bbox={"boxstyle": "round,pad=0.2", "fc": "white", "ec": "#dc2626", "alpha": 0.9},
        )

    ax.set_title(f"Full Knob Inventory - {len(system.param_schema())} Scalar Values", fontsize=13, fontweight="bold")
    ax.set_xlabel("Easting (m)")
    ax.set_ylabel("Northing (m)")
    ax.ticklabel_format(style="plain", useOffset=False)
    ax.set_aspect("equal")
    plt.tight_layout()
    return fig


def _short_labels(node_ids) -> dict[str, str]:
    labels = {}
    for node_id in node_ids:
        if node_id.startswith("HW_"):
            labels[node_id] = node_id[3:]
        elif node_id.startswith("RES_"):
            labels[node_id] = node_id[4:]
        elif node_id.startswith("RF_"):
            labels[node_id] = f"RF:{node_id[3:7]}"
        elif node_id.startswith("Sink_"):
            labels[node_id] = node_id[5:]
        else:
            labels[node_id] = node_id
    return labels


def kattakurgan_policy_variants(timesteps: int) -> list[PolicyVariant]:
    """Run the three manual Kattakurgan SLOP policy variants."""
    specs = [
        (10.0, 400e6, 600e6, 0.05, "Conservative (low vr, high zones, low buf_coef)"),
        (50.7, 133e6, 534e6, 0.2, "Baseline (default SLOP)"),
        (50.7, 100e6, 200e6, 0.8, "Aggressive (low zones, high buf_coef)"),
    ]
    return [_run_kattakurgan_policy(*spec, timesteps=timesteps) for spec in specs]


def _run_kattakurgan_policy(
    vr: float,
    v1: float,
    v2: float,
    buffer_coef: float,
    label: str,
    *,
    timesteps: int,
) -> PolicyVariant:
    system = create_zrb_system(use_canal_losses=True)
    apply_static_demand_splitting(system, verbose=False)

    reservoir = system.nodes["RES_Kattakurgan"]
    object.__setattr__(
        reservoir,
        "release_policy",
        ZRBReleaseRule(
            vr=(vr,) * 12,
            v1=(v1,) * 12,
            v2=(v2,) * 12,
            buffer_coef=(buffer_coef,) * 12,
            flood_coef=(1.0,) * 12,
        ),
    )

    system.validate()
    system.simulate(timesteps)

    storage = _storage_series(reservoir, timesteps)
    karmana = system.nodes["HW_Karmana"]
    karmana_flow = [karmana.trace(WaterReceived, field="amount").get(t, 0.0) / MM3 for t in range(timesteps)]
    deficit = sum(system.nodes[d].trace(DeficitRecorded, field="deficit").sum() for d in DEFAULT_DISTRICTS) / MM3
    spillage = reservoir.trace(WaterSpilled).sum() / MM3

    return PolicyVariant(label=label, storage=storage, karmana_flow=karmana_flow, deficit=deficit, spillage=spillage)


def _storage_series(reservoir, timesteps: int) -> list[float]:
    storage = []
    current = reservoir.initial_storage
    for t in range(timesteps):
        released = reservoir.trace(WaterReleased).get(t, 0.0)
        received = reservoir.trace(WaterReceived, field="amount").get(t, 0.0)
        spilled = reservoir.trace(WaterSpilled).get(t, 0.0)
        current = max(0.0, min(current + received - released - spilled, reservoir.capacity))
        storage.append(current / MM3)
    return storage


def plot_release_sensitivity(
    variants: list[PolicyVariant],
    timesteps: int,
) -> plt.Figure:
    """Plot Kattakurgan storage and HW_Karmana flow for policy variants."""
    dates = pd.date_range("2017-01-01", periods=timesteps, freq="D")
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))

    for variant, color in zip(variants, _SERIES_COLORS, strict=False):
        axes[0].plot(dates, variant.storage, label=variant.label, color=color, linewidth=1.5)
        axes[1].plot(dates, variant.karmana_flow, label=variant.label, color=color, linewidth=1.5, alpha=0.8)

    axes[0].set_ylabel("Kattakurgan Storage (Mm3)")
    axes[0].set_title("Reservoir Storage Trajectory")
    axes[1].set_ylabel("Flow at HW_Karmana (Mm3/day)")
    axes[1].set_title("Downstream Flow")

    for ax in axes:
        ax.legend(fontsize=8)
        ax.tick_params(axis="x", rotation=45)

    plt.tight_layout()
    return fig


def release_comparison_table(variants: list[PolicyVariant]) -> pd.DataFrame:
    """Build the manual Kattakurgan policy comparison table."""
    return pd.DataFrame(
        [
            {
                "Variant": variant.label,
                "Total Ag. Deficit (Mm3)": f"{variant.deficit:,.0f}",
                "Kattakurgan Spillage (Mm3)": f"{variant.spillage:,.0f}",
            }
            for variant in variants
        ]
    )


def narpay_equity_variants(
    baseline: WaterSystem,
    timesteps: int,
) -> list[PolicyVariant]:
    """Run baseline and two manual HW_Narpay split variants."""
    baseline_ratio = _narpay_confluence_ratio(baseline)
    return [
        _run_narpay_ratio(baseline_ratio, "Baseline static ratio", timesteps),
        _run_narpay_ratio(0.20, "More to Narpay (20% to Confluence)", timesteps),
        _run_narpay_ratio(0.60, "More downstream (60% to Confluence)", timesteps),
    ]


def _narpay_confluence_ratio(system: WaterSystem) -> float:
    policy = system.nodes["HW_Narpay"].split_policy
    idx = next(i for i, target in enumerate(policy.targets) if "HW_Confluence" in target)
    return policy.ratios[0][idx]


def _run_narpay_ratio(
    confluence_ratio: float,
    label: str,
    timesteps: int,
) -> PolicyVariant:
    system = create_zrb_system(use_canal_losses=True)
    apply_static_demand_splitting(system, verbose=False)

    splitter = system.nodes["HW_Narpay"]
    targets = splitter.split_policy.targets
    confluence_idx = next(i for i, target in enumerate(targets) if "HW_Confluence" in target)
    narpay_idx = 1 - confluence_idx
    ratios = [0.0, 0.0]
    ratios[confluence_idx] = confluence_ratio
    ratios[narpay_idx] = 1.0 - confluence_ratio
    object.__setattr__(
        splitter,
        "split_policy",
        MonthlyDistribution(targets=targets, ratios=tuple(tuple(ratios) for _ in range(365))),
    )

    system.validate()
    system.simulate(timesteps)
    deficits = {
        district: system.nodes[district].trace(DeficitRecorded, field="deficit").sum() / MM3
        for district in DEFAULT_DISTRICTS
    }
    return PolicyVariant(label=label, deficits=deficits)


def plot_narpay_equity(
    variants: list[PolicyVariant],
    districts: list[str] | None = None,
) -> plt.Figure:
    """Plot per-district deficits for manual HW_Narpay split variants."""
    districts = districts or list(DEFAULT_DISTRICTS)
    x = np.arange(len(districts))
    width = 0.25

    fig, ax = plt.subplots(figsize=(10, 4.5))
    for i, variant in enumerate(variants):
        vals = [variant.deficits[d] for d in districts]
        ax.bar(x + (i - 1) * width, vals, width, label=variant.label, color=_SERIES_COLORS[i])

    ax.set_xlabel("District")
    ax.set_ylabel("Cumulative Deficit (Mm3)")
    ax.set_title("Per-District Deficit Under Different HW_Narpay Allocations")
    ax.set_xticks(x)
    ax.set_xticklabels(districts, rotation=30, ha="right")
    ax.legend(fontsize=8)
    plt.tight_layout()
    return fig


def front_arrays(result, obj_names: list[str]) -> tuple[np.ndarray, int]:
    """Return objective matrix and front size for an optimization result."""
    front_obj = np.array([[s.scores[name] for name in obj_names] for s in result.solutions])
    return front_obj, len(result.solutions)


def run_coursebook_optimization(
    system: WaterSystem,
    objectives: list,
    obj_names: list[str],
    reference_point: dict[str, float],
    *,
    timesteps: int,
    seed: int = 42,
    smoke_test: bool = True,
    force_rerun: bool = False,
) -> tuple[object, ConvergenceHistory, OptimizationConfig]:
    """Run or load the optimization coursebook's smoke/demo optimization.

    Defaults are intentionally small so renders and tests do not accidentally
    launch a long optimization. Set ``smoke_test=False`` for the demo budget.
    """
    pop_size = 12 if smoke_test else 300
    generations = 2 if smoke_test else 100
    n_workers = 2 if smoke_test else 6
    cache_path = Path(
        "_cache/optimization_coursebook_smoke.pkl" if smoke_test else "_cache/optimization_coursebook_daily.pkl"
    )

    config = OptimizationConfig(
        pop_size=pop_size,
        n_generations=generations,
        seed=seed,
        n_workers=n_workers,
        n_timesteps=timesteps,
    )
    callback, history = make_convergence_callback(np.array([reference_point[name] for name in obj_names]))

    def _run():
        return run_optimization(
            system=system,
            objectives=objectives,
            timesteps=timesteps,
            pop_size=pop_size,
            generations=generations,
            seed=seed,
            n_workers=n_workers,
            verbose=True,
            callback=callback,
        )

    cached = run_or_load(_run, config, force=force_rerun, path=cache_path)
    return cached.result, history, config


def representative_indices(front_obj: np.ndarray, obj_names: list[str]) -> dict[str, int]:
    """Select objective extremes plus a normalized balanced representative."""
    representatives = {
        f"Min {name.split(':')[1].strip() if ':' in name else name}": int(np.argmin(front_obj[:, i]))
        for i, name in enumerate(obj_names)
    }
    obj_min = front_obj.min(axis=0)
    obj_max = front_obj.max(axis=0)
    obj_range = np.where(obj_max - obj_min == 0, 1.0, obj_max - obj_min)
    distances = np.sqrt((((front_obj - obj_min) / obj_range) ** 2).sum(axis=1))
    representatives["Balanced"] = int(np.argmin(distances))
    return representatives


def representative_table(
    front_obj: np.ndarray,
    representatives: dict[str, int],
    obj_names: list[str],
) -> pd.DataFrame:
    """Build representative objective score table."""
    rows = []
    for label, idx in representatives.items():
        row = {"Solution": label}
        for i, name in enumerate(obj_names):
            row[f"{name} (Mm3)"] = f"{front_obj[idx, i] / MM3:,.1f}"
        rows.append(row)
    return pd.DataFrame(rows)


def simulate_representatives(result, representatives: dict[str, int], timesteps: int) -> dict[str, WaterSystem]:
    """Return simulated systems for selected representative solutions."""
    systems = {}
    for label, idx in representatives.items():
        system = result.solutions[idx].to_system()
        system.simulate(timesteps)
        systems[label] = system
    return systems


def plot_representative_district_deficits(
    systems: dict[str, WaterSystem],
    districts: list[str] | None = None,
) -> plt.Figure:
    """Plot per-district deficits for representative Pareto solutions."""
    districts = districts or list(DEFAULT_DISTRICTS)
    labels = list(systems)
    x = np.arange(len(districts))
    width = 0.15

    fig, ax = plt.subplots(figsize=(12, 5))
    for i, label in enumerate(labels):
        vals = [systems[label].nodes[d].trace(DeficitRecorded, field="deficit").sum() / MM3 for d in districts]
        ax.bar(x + i * width, vals, width, label=label, color=_SERIES_COLORS[i % len(_SERIES_COLORS)])

    ax.set_xlabel("District")
    ax.set_ylabel("Cumulative Deficit (Mm3)")
    ax.set_title("Per-District Deficit for Representative Solutions")
    ax.set_xticks(x + width * (len(labels) - 1) / 2)
    ax.set_xticklabels(districts, rotation=30, ha="right")
    ax.legend(fontsize=8)
    plt.tight_layout()
    return fig


def plot_representative_sink_flows(
    systems: dict[str, WaterSystem],
    timesteps: int,
    sink_nodes: list[str] | None = None,
) -> plt.Figure:
    """Plot total sink and powerplant inflows for representative solutions."""
    sink_nodes = sink_nodes or ["Sink_Jizzakh", "Sink_Kashkadarya", "Sink_Navoi", "Powerplant"]
    labels = list(systems)
    x = np.arange(len(sink_nodes))
    width = 0.15

    fig, ax = plt.subplots(figsize=(10, 5))
    for i, label in enumerate(labels):
        vals = []
        for node_id in sink_nodes:
            node = systems[label].nodes[node_id]
            vals.append(sum(node.trace(WaterReceived, field="amount").get(t, 0.0) for t in range(timesteps)) / MM3)
        ax.bar(x + i * width, vals, width, label=label, color=_SERIES_COLORS[i % len(_SERIES_COLORS)])

    ax.set_xlabel("Node")
    ax.set_ylabel("Total Flow Received (Mm3)")
    ax.set_title("Sink and Powerplant Flows for Representative Solutions")
    ax.set_xticks(x + width * (len(labels) - 1) / 2)
    ax.set_xticklabels([n.replace("Sink_", "") for n in sink_nodes], rotation=15, ha="right")
    ax.legend(fontsize=8)
    plt.tight_layout()
    return fig


def selected_parameter_names(result) -> list[str]:
    """Choose readable parameter axes for representative profile plots."""
    all_names = list(result.solutions[0].parameters)
    return (
        [p for p in all_names if "eflow_fraction" in p]
        + [p for p in all_names if "RES_Kattakurgan.release_policy.vr" in p][:4]
        + [p for p in all_names if "RES_Kattakurgan.release_policy.buffer_coef" in p][:4]
        + [p for p in all_names if "RES_Akdarya.release_policy.vr" in p][:4]
    )


def plot_selected_parameter_profiles(
    result,
    representatives: dict[str, int],
    param_bounds: dict[str, tuple[float, float]],
    param_names: list[str] | None = None,
) -> plt.Figure:
    """Plot normalized selected parameter values for representative solutions."""
    param_names = param_names or selected_parameter_names(result)
    lower = np.array([param_bounds[p][0] for p in param_names])
    upper = np.array([param_bounds[p][1] for p in param_names])
    x = np.arange(len(param_names))

    fig, ax = plt.subplots(figsize=(12, 5))
    for i, (label, idx) in enumerate(representatives.items()):
        params = result.solutions[idx].parameters
        vals = np.array([params[p] for p in param_names])
        normalized = (vals - lower) / (upper - lower)
        ax.scatter(x, normalized, label=label, s=60, zorder=3, color=_SERIES_COLORS[i % len(_SERIES_COLORS)])
        ax.plot(x, normalized, alpha=0.3, color=_SERIES_COLORS[i % len(_SERIES_COLORS)])

    ax.set_xticks(x)
    ax.set_xticklabels([p.split(".")[-1] for p in param_names], rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Normalised Value [0, 1]")
    ax.set_title("Decision Variables Across Representative Solutions")
    ax.legend(fontsize=8, loc="upper right")
    ax.set_ylim(-0.05, 1.05)
    plt.tight_layout()
    return fig
