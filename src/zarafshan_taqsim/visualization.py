"""Visualization and reporting helpers for Zarafshan River Basin simulations.

Extracts common notebook display patterns into reusable functions:
water balance tables, district summaries, system dashboards, and
scenario comparison tables.
"""

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from taqsim import Reach, Splitter, WaterSystem
from taqsim.node.events import DeficitRecorded, WaterLost, WaterPassedThrough, WaterReceived
from taqsim.time import Frequency, Timestep

from zarafshan_taqsim.analysis import WaterBalance
from zarafshan_taqsim.data import DEFAULT_DISTRICTS, SECONDS_PER_MONTH

SECONDS_PER_DAY = 86_400


def _detect_frequency(timesteps: int) -> tuple[float, float, bool]:
    """Detect frequency from timestep count.

    Returns:
        Tuple of (n_years, seconds_per_step, is_daily).
    """
    if timesteps > 365:
        return timesteps / 365.25, SECONDS_PER_DAY, True
    return timesteps / 12, SECONDS_PER_MONTH, False


def _requirement_series(system: WaterSystem, demand_id: str, timesteps: int) -> np.ndarray:
    """Return the demand node requirement series in system timestep units.

    Uses the node's attached TimeSeries rather than the raw monthly loader so
    the helper stays consistent with both daily and monthly simulations.
    """
    node = system.nodes[demand_id]
    if getattr(node, "requirement", None) is None:
        return np.zeros(timesteps)

    system_freq = getattr(system, "frequency", Frequency.DAILY)
    if not hasattr(system_freq, "value"):
        system_freq = Frequency.DAILY

    return np.array([node.requirement[Timestep(t, frequency=system_freq)] for t in range(timesteps)])


# ---------------------------------------------------------------------------
# 1. Annual water balance table
# ---------------------------------------------------------------------------


def print_annual_water_balance(
    wb: WaterBalance,
    timesteps: int = 72,
    title: str = "Average Annual Water Balance (2017\u20132022)",
) -> None:
    """Print a formatted annual water balance table.

    Displays total and average-annual volumes (Mm\u00b3) alongside each
    component's share of total inflow.

    Args:
        wb: Computed water balance for the simulation period.
        timesteps: Number of timesteps in the simulation.
        title: Header printed above the table.
    """
    n_years, _, _ = _detect_frequency(timesteps)

    print(title)
    print("=" * len(title))
    print(f"{'':30s} {'Total (Mm\u00b3)':>14s} {'Annual (Mm\u00b3)':>14s} {'% Inflow':>11s}")
    print("-" * 71)

    rows: list[tuple[str, float | None, bool | None]] = [
        ("Inflows", None, None),
        ("  River + Runoff", wb.total_inflow, True),
        ("", None, None),
        ("Beneficial Use (mass balance)", None, None),
        ("  Consumed by districts (crop use)", wb.total_consumed, True),
        ("  Sink outflow", wb.sink_outflow, True),
        ("", None, None),
        ("Losses", None, None),
        ("  Canal seepage", wb.seepage_loss, True),
        ("  Reservoir evaporation", wb.reservoir_evaporation_loss, True),
        ("  Demand inefficiency loss", wb.demand_inefficiency_loss, True),
        ("  Canal evaporation", wb.evaporation_loss, True),
        ("  Canal operational", wb.operational_loss, True),
        ("  Edge overflow", wb.capacity_exceeded_loss, True),
        ("  Total losses", wb.total_losses, True),
        ("", None, None),
        ("Storage", None, None),
        ("  Reservoir \u0394Storage", wb.reservoir_storage_change, True),
        ("", None, None),
        ("Closure error", wb.closure_error, True),
        ("", None, None),
        ("Demand Context (not mass balance)", None, None),
        ("  Total agricultural demand", wb.total_demand, True),
        ("  Gross district delivery", wb.total_delivered, True),
        ("  Effective delivery", wb.effective_delivery, True),
        ("  Over-delivery", wb.over_delivery, True),
    ]

    for label, val, _show_pct in rows:
        if val is None:
            print(f"{label}")
        else:
            pct = val / wb.total_inflow * 100 if wb.total_inflow != 0 else 0.0
            print(f"{label:<30} {val / 1e6:>14,.1f} {val / n_years / 1e6:>14,.1f} {pct:>11.1f}%")

    if wb.total_demand > 0:
        demand_satisfaction = wb.effective_delivery / wb.total_demand * 100
        print()
        print(
            "Demand satisfaction (effective delivery / total agricultural demand): "
            f"{demand_satisfaction:.1f}%"
        )
        print("Note: 'Consumed by districts (crop use)' is net consumptive use, not total demand.")


# ---------------------------------------------------------------------------
# 2. Per-district summary
# ---------------------------------------------------------------------------


def print_district_summary(
    system: WaterSystem,
    demand_ids: list[str] | None = None,
    timesteps: int = 72,
    title: str = "Per-District Annual Average: Demand, Supply, Deficit",
) -> dict[str, dict]:
    """Print per-district demand, delivery, and deficit statistics.

    Args:
        system: Simulated WaterSystem with event traces.
        demand_ids: District node IDs to report. Defaults to DEFAULT_DISTRICTS.
        timesteps: Number of timesteps to analyze.
        title: Header printed above the table.

    Returns:
        Dictionary mapping district ID to a dict with keys:
        ``"demand"``, ``"delivered"``, ``"deficit"`` (numpy arrays) and
        ``"total_demand"``, ``"total_delivered"``, ``"total_deficit"`` (floats).
    """
    if demand_ids is None:
        demand_ids = list(DEFAULT_DISTRICTS)

    n_years, _, _ = _detect_frequency(timesteps)
    district_data: dict[str, dict] = {}

    print(title)
    print("=" * len(title))
    print(
        f"{'District':<20} {'Demand (Mm\u00b3/yr)':>16} {'Delivered (Mm\u00b3/yr)':>18} "
        f"{'Deficit (Mm\u00b3/yr)':>17} {'Satisfaction':>12}"
    )
    print("-" * 85)

    for did in demand_ids:
        demand_ts = _requirement_series(system, did, timesteps)
        node = system.nodes[did]
        delivered_ts = np.array([node.trace(WaterReceived).get(t, 0.0) for t in range(timesteps)])
        deficit_ts = np.array([node.trace(DeficitRecorded, field="deficit").get(t, 0.0) for t in range(timesteps)])

        total_demand = demand_ts.sum()
        total_delivered = delivered_ts.sum()
        total_deficit = deficit_ts.sum()
        satisfaction = (1 - total_deficit / total_demand) * 100 if total_demand > 0 else 100.0

        district_data[did] = {
            "demand": demand_ts,
            "delivered": delivered_ts,
            "deficit": deficit_ts,
            "total_demand": total_demand,
            "total_delivered": total_delivered,
            "total_deficit": total_deficit,
        }

        print(
            f"{did:<20} {total_demand / n_years / 1e6:>16,.1f} "
            f"{total_delivered / n_years / 1e6:>18,.1f} "
            f"{total_deficit / n_years / 1e6:>17,.1f} {satisfaction:>11.1f}%"
        )

    return district_data


# ---------------------------------------------------------------------------
# 3. System dashboard (4-panel Plotly figure)
# ---------------------------------------------------------------------------


def plot_system_dashboard(
    wb: WaterBalance,
    system: WaterSystem,
    demand_ids: list[str] | None = None,
    timesteps: int = 72,
    title: str = "System Water Balance Dashboard",
    start_year: int = 2017,
) -> go.Figure:
    """Create a 4-row Plotly dashboard of system water flows.

    Panels:
        1. Inflow, delivery, and losses at the model timestep.
        2. Cumulative water balance components.
        3. Per-district annual demand vs. delivery.
        4. Powerplant flow vs. minimum-flow threshold.

    Args:
        wb: Computed water balance.
        system: Simulated WaterSystem.
        demand_ids: District node IDs. Defaults to DEFAULT_DISTRICTS.
        timesteps: Number of timesteps to analyze.
        title: Overall figure title.
        start_year: Calendar year of the first timestep.

    Returns:
        Plotly Figure object (call ``.show()`` to render).
    """
    if demand_ids is None:
        demand_ids = list(DEFAULT_DISTRICTS)

    # Shared x-axis labels
    n_years, seconds_per_step, is_daily = _detect_frequency(timesteps)
    if is_daily:
        from datetime import date, timedelta

        start = date(start_year, 1, 1)
        x_labels = [str(start + timedelta(days=t)) for t in range(timesteps)]
    else:
        x_labels = [f"{start_year + t // 12}-{(t % 12) + 1:02d}" for t in range(timesteps)]

    flow_title = "Daily Inflow / Delivery / Losses" if is_daily else "Monthly Inflow / Delivery / Losses"

    fig = make_subplots(
        rows=4,
        cols=1,
        subplot_titles=(
            flow_title,
            "Cumulative Water Balance",
            "District Demand vs Delivery (annual average)",
            "Powerplant Flow vs Minimum Threshold",
        ),
        shared_xaxes=False,
        vertical_spacing=0.06,
    )

    # ------------------------------------------------------------------
    # Row 1: Flows at the model timestep
    # ------------------------------------------------------------------
    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=wb.monthly_inflow / 1e6,
            name="Inflow",
            line={"color": "#3498db"},
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=wb.monthly_delivered / 1e6,
            name="Delivery",
            line={"color": "#2ecc71"},
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=wb.monthly_losses / 1e6,
            name="Losses",
            line={"color": "#e74c3c"},
        ),
        row=1,
        col=1,
    )
    fig.update_yaxes(title_text="Mm\u00b3/day" if is_daily else "Mm\u00b3/month", row=1, col=1)

    # ------------------------------------------------------------------
    # Row 2: Cumulative balance
    # ------------------------------------------------------------------
    cum_inflow = np.cumsum(wb.monthly_inflow) / 1e6
    cum_delivered = np.cumsum(wb.monthly_delivered) / 1e6
    cum_losses = np.cumsum(wb.monthly_losses) / 1e6

    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=cum_inflow,
            name="Cum. Inflow",
            line={"color": "#3498db", "dash": "dot"},
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=cum_delivered,
            name="Cum. Delivery",
            line={"color": "#2ecc71", "dash": "dot"},
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=cum_losses,
            name="Cum. Losses",
            line={"color": "#e74c3c", "dash": "dot"},
        ),
        row=2,
        col=1,
    )
    fig.update_yaxes(title_text="Cumulative Mm\u00b3", row=2, col=1)

    # ------------------------------------------------------------------
    # Row 3: District demand vs delivery
    # ------------------------------------------------------------------
    district_labels: list[str] = []
    annual_demand: list[float] = []
    annual_effective_delivery: list[float] = []
    annual_over_delivery: list[float] = []

    for did in demand_ids:
        demand_ts = _requirement_series(system, did, timesteps)
        node = system.nodes[did]
        delivered_ts = np.array([node.trace(WaterReceived).get(t, 0.0) for t in range(timesteps)])
        effective_ts = np.minimum(delivered_ts, demand_ts)
        over_ts = np.maximum(0.0, delivered_ts - demand_ts)

        district_labels.append(did)
        annual_demand.append(demand_ts.sum() / n_years / 1e6)
        annual_effective_delivery.append(effective_ts.sum() / n_years / 1e6)
        annual_over_delivery.append(over_ts.sum() / n_years / 1e6)

    fig.add_trace(
        go.Bar(
            x=district_labels,
            y=annual_effective_delivery,
            name="Effective delivery",
            marker_color="#2ecc71",
            legendgroup="district_summary",
        ),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            x=district_labels,
            y=annual_over_delivery,
            name="Over-delivery",
            marker_color="#f39c12",
            opacity=0.8,
            legendgroup="district_summary",
        ),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=district_labels,
            y=annual_demand,
            name="Demand",
            mode="lines+markers",
            line={"color": "#34495e", "width": 2},
            marker={"size": 8},
            legendgroup="district_summary",
        ),
        row=3,
        col=1,
    )
    fig.update_yaxes(title_text="Mm\u00b3/yr", row=3, col=1)
    fig.update_xaxes(title_text="District", type="category", row=3, col=1)

    # ------------------------------------------------------------------
    # Row 4: Powerplant flow
    # ------------------------------------------------------------------
    pp = system.nodes["Powerplant"]
    pp_flow = np.array([pp.trace(WaterPassedThrough, field="amount").get(t, 0.0) for t in range(timesteps)])
    pp_flow_m3s = pp_flow / seconds_per_step

    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=pp_flow_m3s,
            name="Powerplant flow",
            line={"color": "#8e44ad"},
        ),
        row=4,
        col=1,
    )
    fig.add_hline(
        y=15.0,
        line_dash="dash",
        line_color="red",
        annotation_text="15 m\u00b3/s minimum",
        row=4,
        col=1,
    )
    fig.update_yaxes(title_text="m\u00b3/s", row=4, col=1)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    fig.update_layout(
        height=1200,
        barmode="stack",
        title_text=title,
        showlegend=True,
    )

    fig.update_xaxes(matches="x", row=2, col=1)
    fig.update_xaxes(matches="x", row=4, col=1)
    fig.update_xaxes(showticklabels=False, row=1, col=1)
    fig.update_xaxes(showticklabels=False, row=2, col=1)
    fig.update_xaxes(title_text="Date", row=4, col=1)

    return fig


# ---------------------------------------------------------------------------
# 4. Water balance comparison table
# ---------------------------------------------------------------------------


def print_water_balance_comparison(
    wb_a: WaterBalance,
    wb_b: WaterBalance,
    timesteps: int = 72,
    labels: tuple[str, str] = ("Baseline", "Tuned"),
) -> None:
    """Print a side-by-side comparison of two water balance scenarios.

    Volumes are shown as average-annual Mm\u00b3/yr. Efficiency rows use the
    exact labels ``"System efficiency"`` and ``"Effective efficiency"`` for
    percentage formatting -- substring matching is explicitly avoided.

    Args:
        wb_a: First (baseline) water balance.
        wb_b: Second (tuned) water balance.
        timesteps: Number of timesteps.
        labels: Display names for the two scenarios.
    """
    n_years, _, _ = _detect_frequency(timesteps)
    label_a, label_b = labels

    print(f"Water Balance Comparison: {label_a} vs {label_b}")
    print("=" * 80)
    print(f"{'Component':<30} {label_a + ' (Mm\u00b3/yr)':>19} {label_b + ' (Mm\u00b3/yr)':>19} {'Change':>9}")
    print("-" * 80)

    comparisons: list[tuple[str, float, float]] = [
        ("Inflow", wb_a.total_inflow, wb_b.total_inflow),
        ("Consumed by districts", wb_a.total_consumed, wb_b.total_consumed),
        ("Sink outflow", wb_a.sink_outflow, wb_b.sink_outflow),
        ("Canal seepage", wb_a.seepage_loss, wb_b.seepage_loss),
        ("Reservoir evaporation", wb_a.reservoir_evaporation_loss, wb_b.reservoir_evaporation_loss),
        ("Demand inefficiency", wb_a.demand_inefficiency_loss, wb_b.demand_inefficiency_loss),
        ("Canal evaporation", wb_a.evaporation_loss, wb_b.evaporation_loss),
        ("Canal operational", wb_a.operational_loss, wb_b.operational_loss),
        ("Edge overflow", wb_a.capacity_exceeded_loss, wb_b.capacity_exceeded_loss),
        ("Total losses", wb_a.total_losses, wb_b.total_losses),
        ("Reservoir \u0394Storage", wb_a.reservoir_storage_change, wb_b.reservoir_storage_change),
        ("Closure error", wb_a.closure_error, wb_b.closure_error),
        ("System efficiency", wb_a.system_efficiency, wb_b.system_efficiency),
        ("Effective efficiency", wb_a.effective_efficiency, wb_b.effective_efficiency),
        ("Unmet demand", wb_a.total_deficit, wb_b.total_deficit),
    ]

    for label, base_val, tuned_val in comparisons:
        # EXACT match -- never use substring matching (e.g. ``in label``)
        if label in ("System efficiency", "Effective efficiency"):
            print(
                f"{label:<30} {base_val * 100:>19.1f}% {tuned_val * 100:>19.1f}% {(tuned_val - base_val) * 100:>+9.1f}%"
            )
        else:
            change_pct = (tuned_val - base_val) / abs(base_val) * 100 if base_val != 0 else 0.0
            print(
                f"{label:<30} {base_val / n_years / 1e6:>20,.1f} "
                f"{tuned_val / n_years / 1e6:>20,.1f} "
                f"{change_pct:>+9.1f}%"
            )


# ---------------------------------------------------------------------------
# 5. District comparison table
# ---------------------------------------------------------------------------


def print_district_comparison(
    system_a: WaterSystem,
    system_b: WaterSystem,
    demand_ids: list[str] | None = None,
    timesteps: int = 72,
    labels: tuple[str, str] = ("Baseline", "Tuned"),
) -> None:
    """Print a per-district comparison between two simulation scenarios.

    Shows demand satisfaction and deficit change for each district.

    Args:
        system_a: First simulated system.
        system_b: Second simulated system.
        demand_ids: District node IDs. Defaults to DEFAULT_DISTRICTS.
        timesteps: Number of timesteps to analyze.
        labels: Display names for the two scenarios.
    """
    if demand_ids is None:
        demand_ids = list(DEFAULT_DISTRICTS)

    n_years, _, _ = _detect_frequency(timesteps)
    label_a, label_b = labels

    print(f"District Comparison: {label_a} vs {label_b}")
    print("=" * 90)
    print(
        f"{'District':<20} {'Demand (Mm\u00b3/yr)':>16} "
        f"{label_a + ' sat.':>12} {label_b + ' sat.':>12} "
        f"{'\u0394 Deficit (Mm\u00b3/yr)':>18}"
    )
    print("-" * 90)

    for did in demand_ids:
        demand_ts = _requirement_series(system_a, did, timesteps)
        total_demand = demand_ts.sum()

        node_a = system_a.nodes[did]
        deficit_a = sum(node_a.trace(DeficitRecorded, field="deficit").get(t, 0.0) for t in range(timesteps))
        sat_a = (1 - deficit_a / total_demand) * 100 if total_demand > 0 else 100.0

        node_b = system_b.nodes[did]
        deficit_b = sum(node_b.trace(DeficitRecorded, field="deficit").get(t, 0.0) for t in range(timesteps))
        sat_b = (1 - deficit_b / total_demand) * 100 if total_demand > 0 else 100.0

        delta_deficit = (deficit_b - deficit_a) / n_years / 1e6

        print(
            f"{did:<20} {total_demand / n_years / 1e6:>16,.1f} {sat_a:>11.1f}% {sat_b:>11.1f}% {delta_deficit:>+18,.1f}"
        )


# ---------------------------------------------------------------------------
# 6. Powerplant statistics
# ---------------------------------------------------------------------------


def print_powerplant_stats(
    system: WaterSystem,
    timesteps: int = 72,
    min_flow_m3s: float = 15.0,
    label: str = "Powerplant",
) -> None:
    """Print powerplant flow statistics relative to a minimum-flow threshold.

    Args:
        system: Simulated WaterSystem.
        timesteps: Number of timesteps.
        min_flow_m3s: Minimum acceptable flow in m\u00b3/s.
        label: Display name for the powerplant node.
    """
    pp = system.nodes["Powerplant"]
    pp_flow = np.array([pp.trace(WaterPassedThrough, field="amount").get(t, 0.0) for t in range(timesteps)])
    _, seconds_per_step, is_daily = _detect_frequency(timesteps)
    pp_flow_m3s = pp_flow / seconds_per_step

    months_below = int(np.sum(pp_flow_m3s < min_flow_m3s))
    mean_flow = float(np.mean(pp_flow_m3s))
    min_observed = float(np.min(pp_flow_m3s))
    max_observed = float(np.max(pp_flow_m3s))

    print(f"{label} Flow Statistics")
    print("=" * 45)
    print(f"  {'Min threshold:':<24} {min_flow_m3s:>10.1f} m\u00b3/s")
    print(f"  {'Mean flow:':<24} {mean_flow:>10.1f} m\u00b3/s")
    print(f"  {'Min flow:':<24} {min_observed:>10.1f} m\u00b3/s")
    print(f"  {'Max flow:':<24} {max_observed:>10.1f} m\u00b3/s")
    print(f"  {'Steps below threshold:':<24} {months_below:>10d} / {timesteps}")


# ---------------------------------------------------------------------------
# 7. Powerplant comparison
# ---------------------------------------------------------------------------


def print_powerplant_comparison(
    system_a: WaterSystem,
    system_b: WaterSystem,
    timesteps: int = 72,
    min_flow_m3s: float = 15.0,
    labels: tuple[str, str] = ("Baseline", "Tuned"),
) -> None:
    """Print a side-by-side powerplant flow comparison for two scenarios.

    Args:
        system_a: First simulated system.
        system_b: Second simulated system.
        timesteps: Number of timesteps.
        min_flow_m3s: Minimum acceptable flow in m\u00b3/s.
        labels: Display names for the two scenarios.
    """
    label_a, label_b = labels

    def _stats(system: WaterSystem) -> dict[str, float]:
        pp = system.nodes["Powerplant"]
        pp_flow = np.array([pp.trace(WaterPassedThrough, field="amount").get(t, 0.0) for t in range(timesteps)])
        _, seconds_per_step, _ = _detect_frequency(timesteps)
        pp_flow_m3s = pp_flow / seconds_per_step
        return {
            "mean": float(np.mean(pp_flow_m3s)),
            "min": float(np.min(pp_flow_m3s)),
            "max": float(np.max(pp_flow_m3s)),
            "months_below": int(np.sum(pp_flow_m3s < min_flow_m3s)),
        }

    sa = _stats(system_a)
    sb = _stats(system_b)

    print(f"Powerplant Comparison: {label_a} vs {label_b}")
    print("=" * 65)
    print(f"{'Metric':<26} {label_a:>14} {label_b:>14} {'Change':>9}")
    print("-" * 65)

    for metric, unit in [("mean", "m\u00b3/s"), ("min", "m\u00b3/s"), ("max", "m\u00b3/s")]:
        val_a = sa[metric]
        val_b = sb[metric]
        delta = val_b - val_a
        print(f"  {metric.capitalize() + ' flow':<24} {val_a:>12.1f} {val_b:>14.1f} {delta:>+9.1f} {unit}")

    print(
        f"  {'Steps below threshold':<24} {sa['months_below']:>12d} "
        f"{sb['months_below']:>14d} {sb['months_below'] - sa['months_below']:>+9d}"
    )


# ---------------------------------------------------------------------------
# 8. Notebook-first coursebook figures and summary tables
# ---------------------------------------------------------------------------


def plot_static_ratio_network(
    system: WaterSystem | None = None,
    use_canal_losses: bool = True,
    title: str = "Static-Tuned Splitting Ratios",
) -> plt.Figure:
    """Plot the static splitter ratios on the geographic ZRB network layout."""
    from zarafshan_taqsim.network import (
        NODE_COLORS,
        NODE_SIZES,
        _get_geographic_positions,
        apply_static_demand_splitting,
        create_zrb_system,
    )
    from zarafshan_taqsim.strategies import MonthlyDistribution

    if system is None:
        system = create_zrb_system(use_canal_losses=use_canal_losses)
        apply_static_demand_splitting(system, verbose=False)

    graph = nx.DiGraph()
    node_colors: list[str] = []
    node_sizes: list[int] = []

    for node_id, node in system.nodes.items():
        graph.add_node(node_id)
        node_colors.append(NODE_COLORS.get(type(node), "#95a5a6"))
        node_sizes.append(NODE_SIZES.get(type(node), 500))

    for edge in system.edges.values():
        graph.add_edge(edge.source, edge.target)

    edge_ratios: dict[tuple[str, str], float] = {}
    for node_id, node in system.nodes.items():
        if not isinstance(node, Splitter):
            continue
        policy = getattr(node, "split_policy", None)
        if not isinstance(policy, MonthlyDistribution):
            continue
        for target, ratio in zip(policy.targets, policy.ratios[0], strict=True):
            edge_ratios[(node_id, target)] = float(ratio)

    pos = _get_geographic_positions(system)
    for node_id in graph.nodes():
        pos.setdefault(node_id, (250000, 4420000))

    fig, ax = plt.subplots(figsize=(16, 12))

    non_splitter_edges = [(u, v) for u, v in graph.edges() if (u, v) not in edge_ratios]
    nx.draw_networkx_edges(
        graph,
        pos,
        edgelist=non_splitter_edges,
        ax=ax,
        edge_color="#d5d8dc",
        width=1.0,
        arrows=True,
        arrowsize=10,
        connectionstyle="arc3,rad=0.05",
        alpha=0.5,
    )

    for (source, target), ratio in edge_ratios.items():
        width = max(1.0, ratio * 12)
        color = "#2c3e50" if ratio >= 0.3 else "#3498db" if ratio >= 0.1 else "#aab7b8"
        nx.draw_networkx_edges(
            graph,
            pos,
            edgelist=[(source, target)],
            ax=ax,
            width=width,
            edge_color=color,
            arrows=True,
            arrowsize=12,
            connectionstyle="arc3,rad=0.05",
            alpha=0.8,
        )

    for (source, target), ratio in edge_ratios.items():
        x_mid = (pos[source][0] + pos[target][0]) / 2
        y_mid = (pos[source][1] + pos[target][1]) / 2
        dx = pos[target][0] - pos[source][0]
        dy = pos[target][1] - pos[source][1]
        length = max((dx**2 + dy**2) ** 0.5, 1e-6)
        offset_x = -dy / length * 2500
        offset_y = dx / length * 2500
        ax.annotate(
            f"{ratio:.0%}",
            (x_mid + offset_x, y_mid + offset_y),
            fontsize=7,
            ha="center",
            va="center",
            fontweight="bold",
            bbox={"boxstyle": "round,pad=0.15", "fc": "white", "ec": "#bdc3c7", "alpha": 0.9},
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

    labels: dict[str, str] = {}
    for node_id in graph.nodes():
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

    nx.draw_networkx_labels(graph, pos, labels, ax=ax, font_size=8, font_weight="bold")

    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.axis("off")
    fig.tight_layout()
    return fig


def build_baseline_overview_table(
    wb_uniform: WaterBalance,
    wb_static: WaterBalance,
    wb_monthly: WaterBalance,
) -> "pd.io.formats.style.Styler":
    """Build the coursebook comparison table for the three baseline strategies."""

    def _delta(base: float, tuned: float, is_pct: bool = False) -> str:
        if is_pct:
            return f"{tuned - base:+.1f} pp"
        if abs(base) < 1e-6:
            return "—"
        return f"{((tuned - base) / abs(base) * 100):+.1f}%"

    overview = pd.DataFrame(
        {
            "Metric": [
                "Total Inflow (Mm³)",
                "Total Demand (Mm³)",
                "Effective Delivery (Mm³)",
                "Over-Delivery (Mm³)",
                "Total Deficit (Mm³)",
                "Effective Efficiency (%)",
                "Waste Fraction (%)",
                "System Efficiency (%)",
            ],
            "Uniform": [
                f"{wb_uniform.total_inflow / 1e6:,.0f}",
                f"{wb_uniform.total_demand / 1e6:,.0f}",
                f"{wb_uniform.effective_delivery / 1e6:,.0f}",
                f"{wb_uniform.over_delivery / 1e6:,.0f}",
                f"{wb_uniform.total_deficit / 1e6:,.0f}",
                f"{wb_uniform.effective_efficiency * 100:.1f}",
                f"{wb_uniform.waste_fraction * 100:.1f}",
                f"{wb_uniform.system_efficiency * 100:.1f}",
            ],
            "Static-Tuned": [
                f"{wb_static.total_inflow / 1e6:,.0f}",
                f"{wb_static.total_demand / 1e6:,.0f}",
                f"{wb_static.effective_delivery / 1e6:,.0f}",
                f"{wb_static.over_delivery / 1e6:,.0f}",
                f"{wb_static.total_deficit / 1e6:,.0f}",
                f"{wb_static.effective_efficiency * 100:.1f}",
                f"{wb_static.waste_fraction * 100:.1f}",
                f"{wb_static.system_efficiency * 100:.1f}",
            ],
            "Monthly-Tuned": [
                f"{wb_monthly.total_inflow / 1e6:,.0f}",
                f"{wb_monthly.total_demand / 1e6:,.0f}",
                f"{wb_monthly.effective_delivery / 1e6:,.0f}",
                f"{wb_monthly.over_delivery / 1e6:,.0f}",
                f"{wb_monthly.total_deficit / 1e6:,.0f}",
                f"{wb_monthly.effective_efficiency * 100:.1f}",
                f"{wb_monthly.waste_fraction * 100:.1f}",
                f"{wb_monthly.system_efficiency * 100:.1f}",
            ],
            "Δ Uniform → Monthly": [
                _delta(wb_uniform.total_inflow, wb_monthly.total_inflow),
                _delta(wb_uniform.total_demand, wb_monthly.total_demand),
                _delta(wb_uniform.effective_delivery, wb_monthly.effective_delivery),
                _delta(wb_uniform.over_delivery, wb_monthly.over_delivery),
                _delta(wb_uniform.total_deficit, wb_monthly.total_deficit),
                _delta(wb_uniform.effective_efficiency * 100, wb_monthly.effective_efficiency * 100, is_pct=True),
                _delta(wb_uniform.waste_fraction * 100, wb_monthly.waste_fraction * 100, is_pct=True),
                _delta(wb_uniform.system_efficiency * 100, wb_monthly.system_efficiency * 100, is_pct=True),
            ],
        }
    )

    return (
        overview.style.set_properties(**{"text-align": "right"})
        .set_properties(subset=["Metric"], **{"text-align": "left", "font-weight": "bold"})
        .hide(axis="index")
    )


def plot_baseline_strategy_comparison(
    wb_uniform: WaterBalance,
    wb_static: WaterBalance,
    wb_monthly: WaterBalance,
    timesteps: int = 72,
    title: str = "Three-Way Water Balance Comparison",
) -> go.Figure:
    """Plot the stacked water-balance and metric comparison for all baselines."""
    n_years, _, _ = _detect_frequency(timesteps)
    strategies = ["Uniform", "Static-Tuned", "Monthly-Tuned"]
    water_balances = [wb_uniform, wb_static, wb_monthly]

    components = {
        "Consumed by districts": [w.total_consumed / n_years / 1e6 for w in water_balances],
        "Sink outflow": [w.sink_outflow / n_years / 1e6 for w in water_balances],
        "Canal seepage": [w.seepage_loss / n_years / 1e6 for w in water_balances],
        "Reservoir evaporation": [w.reservoir_evaporation_loss / n_years / 1e6 for w in water_balances],
        "Demand inefficiency": [w.demand_inefficiency_loss / n_years / 1e6 for w in water_balances],
        "Canal evap. + operational": [
            (w.evaporation_loss + w.operational_loss) / n_years / 1e6 for w in water_balances
        ],
        "Edge overflow": [w.capacity_exceeded_loss / n_years / 1e6 for w in water_balances],
        "Reservoir ΔStorage": [max(0, w.reservoir_storage_change) / n_years / 1e6 for w in water_balances],
    }
    colors = {
        "Consumed by districts": "#2ecc71",
        "Sink outflow": "#3498db",
        "Canal seepage": "#e74c3c",
        "Reservoir evaporation": "#f39c12",
        "Demand inefficiency": "#e67e22",
        "Canal evap. + operational": "#d35400",
        "Edge overflow": "#c0392b",
        "Reservoir ΔStorage": "#95a5a6",
    }

    fig = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=("Where Does the Water Go? (Annual Mm³)", "Key Performance Metrics"),
        row_heights=[0.55, 0.45],
        vertical_spacing=0.15,
    )

    for component, values in components.items():
        fig.add_trace(
            go.Bar(
                x=strategies,
                y=values,
                name=component,
                marker_color=colors[component],
                hovertemplate=f"{component}<br>%{{x}}: %{{y:,.0f}} Mm³/yr<extra></extra>",
            ),
            row=1,
            col=1,
        )

    metric_names = ["System\nEfficiency", "Effective\nEfficiency", "Waste\nFraction"]
    metric_values = {
        strategy: [
            water_balance.system_efficiency * 100,
            water_balance.effective_efficiency * 100,
            water_balance.waste_fraction * 100,
        ]
        for strategy, water_balance in zip(strategies, water_balances, strict=True)
    }
    bar_colors = ["#95a5a6", "#3498db", "#2ecc71"]

    for idx, (strategy, values) in enumerate(metric_values.items()):
        fig.add_trace(
            go.Bar(
                x=metric_names,
                y=values,
                name=strategy,
                marker_color=bar_colors[idx],
                showlegend=False,
                hovertemplate=f"{strategy}<br>%{{x}}: %{{y:.1f}}%<extra></extra>",
                text=[f"{v:.1f}%" for v in values],
                textposition="outside",
                textfont_size=10,
            ),
            row=2,
            col=1,
        )

    fig.update_layout(
        barmode="stack",
        height=900,
        legend={"orientation": "h", "yanchor": "bottom", "y": -0.15, "xanchor": "center", "x": 0.5},
        margin={"t": 60, "b": 80},
        title_text=title,
        title_x=0.5,
        legend_tracegroupgap=0,
    )
    fig.update_yaxes(title_text="Annual Volume (Mm³/yr)", row=1, col=1)
    fig.update_yaxes(title_text="Percentage (%)", row=2, col=1)

    for idx, (strategy, color) in enumerate(zip(strategies, bar_colors, strict=True)):
        fig.add_annotation(
            x=1.02,
            y=0.95 - idx * 0.08,
            xref="paper",
            yref="paper",
            text=f'<span style="color:{color}">■</span> {strategy}',
            showarrow=False,
            font={"size": 11},
            xanchor="left",
        )

    return fig


def _reach_loss_timeseries(
    system: WaterSystem,
    timesteps: int,
    start_date: str = "2017-01-01",
) -> tuple[dict[str, float], pd.DataFrame]:
    """Collect per-cause reach losses and return totals plus a timestep table."""
    loss_types = ("seepage", "evaporation", "operational")
    loss_totals = dict.fromkeys(loss_types, 0.0)
    timestep_losses = pd.DataFrame(
        0.0,
        index=pd.date_range(start_date, periods=timesteps, freq="D"),
        columns=loss_types,
    )

    for node in system.nodes.values():
        if not isinstance(node, Reach):
            continue
        for event in node.events_of_type(WaterLost):
            reason = str(event.reason).lower()
            if "seepage" in reason:
                loss_key = "seepage"
            elif "evaporation" in reason:
                loss_key = "evaporation"
            else:
                loss_key = "operational"

            loss_totals[loss_key] += event.amount
            if event.t < timesteps:
                timestep_losses.iloc[event.t, timestep_losses.columns.get_loc(loss_key)] += event.amount

    return loss_totals, timestep_losses


def plot_canal_loss_breakdown(
    system: WaterSystem,
    timesteps: int,
    start_date: str = "2017-01-01",
) -> plt.Figure:
    """Plot total canal losses by type and their monthly aggregates."""
    loss_totals, timestep_losses = _reach_loss_timeseries(system, timesteps, start_date=start_date)
    monthly_losses = timestep_losses.resample("ME").sum()
    total_loss = sum(loss_totals.values())

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    loss_types = ["seepage", "evaporation", "operational"]
    colors = {"seepage": "#e74c3c", "evaporation": "#3498db", "operational": "#f39c12"}

    if total_loss > 0:
        axes[0].pie(
            [loss_totals[loss_type] for loss_type in loss_types],
            labels=[loss_type.capitalize() for loss_type in loss_types],
            autopct="%1.1f%%",
            colors=[colors[loss_type] for loss_type in loss_types],
            startangle=90,
        )
    axes[0].set_title("Loss by Type")

    months = np.arange(len(monthly_losses))
    bottom = np.zeros(len(monthly_losses))
    for loss_type in loss_types:
        values = monthly_losses[loss_type].to_numpy()
        axes[1].bar(
            months,
            values / 1e6,
            bottom=bottom / 1e6,
            label=loss_type.capitalize(),
            color=colors[loss_type],
            alpha=0.8,
            width=1.0,
        )
        bottom += values

    axes[1].set_xlabel("Month")
    axes[1].set_ylabel("Loss (Mm³/month)")
    axes[1].set_title("Monthly Aggregates of Daily Losses")
    axes[1].legend(loc="upper right")

    year_ticks = [idx for idx, ts in enumerate(monthly_losses.index) if ts.month == 1]
    axes[1].set_xticks(year_ticks)
    axes[1].set_xticklabels([str(ts.year) for ts in monthly_losses.index[year_ticks]])

    fig.tight_layout()
    return fig


def plot_top_reach_losses(
    system: WaterSystem,
    top_n: int = 15,
    title: str = "Top Canal Segments by Transmission Loss",
) -> plt.Figure:
    """Plot the highest-loss reach nodes for a simulated system."""

    def _reach_label(reach_id: str) -> str:
        source = next((edge.source for edge in system.edges.values() if edge.target == reach_id), None)
        target = next((edge.target for edge in system.edges.values() if edge.source == reach_id), None)
        if source and target:
            return f"{source} → {target}"
        return reach_id

    reach_losses = {}
    for node_id, node in system.nodes.items():
        if not isinstance(node, Reach):
            continue
        reach_losses[node_id] = sum(event.amount for event in node.events_of_type(WaterLost))

    top_reaches = sorted(reach_losses.items(), key=lambda item: item[1], reverse=True)[:top_n]
    labels = [_reach_label(reach_id) for reach_id, _ in top_reaches]
    values = [loss / 1e6 for _, loss in top_reaches]

    fig, ax = plt.subplots(figsize=(10, 7))
    y_pos = np.arange(len(top_reaches))
    ax.barh(y_pos, values, color="#e74c3c", alpha=0.8)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("Total Loss (Mm³)")
    ax.set_title(title)
    ax.grid(True, alpha=0.3, axis="x")

    fig.tight_layout()
    return fig
