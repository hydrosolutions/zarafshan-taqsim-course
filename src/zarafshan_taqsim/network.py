"""Network construction for Zarafshan River Basin model."""

import inspect
import json
import logging
from collections import defaultdict, deque
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from taqsim import (
    Demand,
    NoLoss,
    Reach,
    Source,
    Splitter,
    Storage,
    TimeSeries,
    WaterSystem,
)
from taqsim.time import Timestep

from zarafshan_taqsim.strategies import (
    CanalLossRule,
    EFlowSplitPolicy,
    EvaporationLossRule,
    Lag,
    MonthlyDistribution,
    PriorityDistribution,
    ZRBReleaseRule,
)

logger = logging.getLogger(__name__)

TOPOLOGY_PATH = Path(__file__).parent.parent.parent / "scratchpad" / "zarafshan_topology.json"
SECONDS_PER_DAY = 86_400

N_TIMESTEPS = 2191  # 6 years × 365 days + 1 leap day (2017-2022)

# Reservoir release rule defaults (SLOP policy)
DEFAULT_RELEASE_FRACTION = 0.20  # Target monthly release as fraction of capacity
BUFFER_ZONE_MULTIPLIER = 2.0  # Buffer zone top = dead_storage × this
CONSERVATION_ZONE_FRACTION = 0.80  # Conservation zone top as fraction of capacity
DEFAULT_BUFFER_COEFFICIENT = 0.20  # Reduced release factor in buffer zone

# Average seconds per month (used to convert capacity fraction → m³/s for vr)
_SECONDS_PER_MONTH = 30.44 * 24 * 3600

# Maps non-natural reach IDs to their downstream demand district(s).
# Reaches that serve no irrigation demand (e.g., Sink_Jizzakh, Powerplant)
# get a floor weight so they still receive a share of water.
REACH_DEMAND_MAPPING: dict[str, tuple[str, ...]] = {
    "R_HW_Ravatkhoza_Mirzapay": ("Mirzapay",),
    "R_HW_Ravatkhoza_HW_Dargom": ("Dargom",),
    "R_HW_Ravatkhoza_Sink_Jizzakh": (),
    "R_HW_AkKaraDarya_Akkaradarya": ("Akkaradarya",),
    "R_HW_Damkhoza_HW_Narpay": ("Narpay",),
    "R_HW_Damkhoza_Miankaltoss": ("Miankaltoss",),
    "R_HW_Damkhoza_RES_Kattakurgan": ("Narpay",),
    "R_HW_Karmana_Karmanakonimex": ("Karmanakonimex",),
    "R_HW_Karmana_Powerplant": (),
}
_NO_DEMAND_FLOOR_M3S = 1.0


def _iter_reachable_demands(system: WaterSystem, start_node_id: str) -> set[str]:
    """Return all downstream Demand node IDs reachable from ``start_node_id``."""
    reachable: set[str] = set()
    queue: deque[str] = deque([start_node_id])
    seen: set[str] = set()

    while queue:
        node_id = queue.popleft()
        if node_id in seen:
            continue
        seen.add(node_id)

        node = system.nodes.get(node_id)
        if isinstance(node, Demand):
            reachable.add(node_id)

        for edge in system.edges.values():
            if edge.source == node_id:
                queue.append(edge.target)

    return reachable


def _downstream_daily_demand(system: WaterSystem, start_node_id: str, timesteps: int) -> np.ndarray:
    """Aggregate downstream demand-node requirements as daily timestep volumes."""
    total = np.zeros(timesteps, dtype=float)
    system_freq = getattr(system, "frequency", None)
    for demand_id in _iter_reachable_demands(system, start_node_id):
        demand_node = system.nodes[demand_id]
        total += np.array(
            [demand_node.requirement[Timestep(t, frequency=system_freq)] for t in range(timesteps)],
            dtype=float,
        )
    return total


def _apply_ratio_floor(weights: list[float], min_ratio: float) -> tuple[float, ...]:
    """Normalize non-negative weights while enforcing a minimum per branch."""
    n = len(weights)
    if n == 0:
        return ()
    if n == 1:
        return (1.0,)
    if min_ratio * n >= 1.0:
        return tuple(1.0 / n for _ in weights)

    total = sum(weights)
    base = [1.0 / n for _ in weights] if total <= 0 else [w / total for w in weights]

    fixed = [max(r, min_ratio) for r in base]
    fixed_total = sum(fixed)
    return tuple(r / fixed_total for r in fixed)


def apply_static_demand_splitting(
    system: WaterSystem,
    min_ratio: float = 0.05,
    verbose: bool = False,
) -> None:
    """Apply one fixed demand-weighted ratio vector to each monthly splitter.

    This is a compatibility wrapper for the coursebook. It only updates
    splitters that currently use ``MonthlyDistribution`` and leaves other
    special policies (for example environmental-flow or priority splitters)
    unchanged.
    """
    timesteps = N_TIMESTEPS

    for node in system.nodes.values():
        if not isinstance(node, Splitter):
            continue

        policy = getattr(node, "split_policy", None)
        if not isinstance(policy, MonthlyDistribution):
            continue

        weights: list[float] = []
        for target in policy.targets:
            demand = _downstream_daily_demand(system, target, timesteps)
            total = float(demand.sum())
            if total <= 0:
                total = _NO_DEMAND_FLOOR_M3S * SECONDS_PER_DAY * timesteps
            weights.append(total)

        ratios = _apply_ratio_floor(weights, min_ratio)
        object.__setattr__(node, "split_policy", MonthlyDistribution(targets=policy.targets, ratios=tuple(ratios for _ in range(365))))

        if verbose:
            logger.info("Applied static demand splitting at %s: %s", node.id, ratios)


def apply_demand_proportional_splitting(
    system: WaterSystem,
    min_ratio: float = 0.05,
    verbose: bool = False,
) -> None:
    """Apply a seasonal monthly demand-weighted schedule on the daily clock.

    Ratios are computed from downstream daily demand by averaging each calendar
    month across the 2017--2022 period, then expanded to a 365-day repeating
    pattern for compatibility with the current daily simulation.
    """
    from zarafshan_taqsim.data import expand_monthly_ratios_to_daily

    timesteps = N_TIMESTEPS
    date_index = pd.date_range("2017-01-01", periods=timesteps, freq="D")

    for node in system.nodes.values():
        if not isinstance(node, Splitter):
            continue

        policy = getattr(node, "split_policy", None)
        if not isinstance(policy, MonthlyDistribution):
            continue

        monthly_weights_by_target: list[list[float]] = []
        for target in policy.targets:
            demand = _downstream_daily_demand(system, target, timesteps)
            if demand.sum() <= 0:
                monthly_weights = [_NO_DEMAND_FLOOR_M3S * _SECONDS_PER_MONTH for _ in range(12)]
            else:
                demand_series = pd.Series(demand, index=date_index)
                monthly_totals = demand_series.resample("ME").sum()
                monthly_weights = []
                for month in range(1, 13):
                    vals = monthly_totals[monthly_totals.index.month == month]
                    monthly_weights.append(float(vals.mean()) if len(vals) else 0.0)
            monthly_weights_by_target.append(monthly_weights)

        monthly_ratios: list[tuple[float, ...]] = []
        for month_idx in range(12):
            month_weights = [target_weights[month_idx] for target_weights in monthly_weights_by_target]
            monthly_ratios.append(_apply_ratio_floor(month_weights, min_ratio))

        daily_ratios = expand_monthly_ratios_to_daily(tuple(monthly_ratios))
        object.__setattr__(node, "split_policy", MonthlyDistribution(targets=policy.targets, ratios=daily_ratios))

        if verbose:
            logger.info("Applied seasonal demand splitting at %s", node.id)


def _compute_demand_weighted_ratios(
    non_natural_reaches: list[str],
) -> tuple[tuple[float, ...], ...]:
    """Compute 365-day demand-weighted ratios for non-natural reaches.

    For each calendar month, the weight of a reach is the average demand (m³/month)
    of its mapped downstream district(s) across all years. Reaches with no mapped
    demand receive a floor weight. The 12 monthly ratios are expanded to 365 daily.

    Args:
        non_natural_reaches: List of reach IDs that are not natural.

    Returns:
        Tuple of 365 tuples, each containing one ratio per non-natural reach.
        Ratios sum to 1.0 per day.
    """
    from zarafshan_taqsim.data import SECONDS_PER_MONTH, expand_monthly_ratios_to_daily, load_demand

    n_reaches = len(non_natural_reaches)
    if n_reaches == 0:
        return ()
    if n_reaches == 1:
        return tuple((1.0,) for _ in range(365))

    # Compute monthly weight per reach (average across years)
    floor_weight = _NO_DEMAND_FLOOR_M3S * SECONDS_PER_MONTH
    monthly_weights: list[list[float]] = []  # [12 months][n_reaches]

    for month in range(12):
        month_weights: list[float] = []
        for reach_id in non_natural_reaches:
            districts = REACH_DEMAND_MAPPING.get(reach_id, ())
            if not districts:
                month_weights.append(floor_weight)
            else:
                # Average demand across years for this calendar month
                total = 0.0
                for district in districts:
                    demand_series = load_demand(district)
                    n_years = len(demand_series) // 12
                    yearly_vals = [demand_series[y * 12 + month] for y in range(n_years)]
                    total += sum(yearly_vals) / len(yearly_vals)
                month_weights.append(total)
        monthly_weights.append(month_weights)

    # Normalize per month → 12 tuples
    monthly_12: list[tuple[float, ...]] = []
    for month_weights in monthly_weights:
        total = sum(month_weights)
        if total > 0:
            monthly_12.append(tuple(w / total for w in month_weights))
        else:
            monthly_12.append(tuple(1.0 / n_reaches for _ in range(n_reaches)))

    # Expand 12 → 365
    return expand_monthly_ratios_to_daily(tuple(monthly_12))


def create_zrb_system(
    use_canal_losses: bool = True,
    use_reservoir_evaporation: bool = True,
) -> WaterSystem:
    """Create the complete Zarafshan River Basin water system.

    Loads topology from JSON (61 nodes, 70 edges), then injects real daily
    timeseries data, release policies, split policies, routing, and losses.

    Args:
        use_canal_losses: If True, apply canal loss rules to Reach nodes. Default True.
        use_reservoir_evaporation: If True, apply evaporation losses to
            reservoirs. Default True.

    Returns:
        Configured WaterSystem ready for simulation.
    """
    system = WaterSystem.from_json(TOPOLOGY_PATH)
    _inject_timeseries_data(system)
    _inject_release_policies(system, use_reservoir_evaporation)
    _inject_split_policies(system)
    _inject_routing_models(system)
    if use_canal_losses:
        _inject_canal_losses(system)
    return system


def _inject_timeseries_data(system: WaterSystem) -> None:
    """Set real daily timeseries data on Source, Demand, and RF nodes.

    All injected values are converted from m³/s to m³/timestep (m³/day for
    daily frequency) so that every node in the network operates in consistent
    volume-per-timestep units.  Without this conversion the Source node would
    output raw m³/s while Storage nodes (via ZRBReleaseRule) output m³/day,
    creating a unit mismatch that breaks mass-balance closure.
    """
    from zarafshan_taqsim.data import (
        SECONDS_PER_DAY,
        SECONDS_PER_MONTH,
        compute_runoff,
        load_demand_raw,
        load_inflow_daily,
        load_precipitation,
        load_runoff_config,
        replicate_monthly_to_daily,
    )

    # Source node: daily observed inflow — convert m³/s → m³/day
    daily_inflow_m3s = load_inflow_daily()
    daily_inflow = [v * SECONDS_PER_DAY for v in daily_inflow_m3s]
    source = system.nodes["Source"]
    object.__setattr__(source, "inflow", TimeSeries(daily_inflow))

    # Demand nodes: monthly rates → daily — convert m³/s → m³/day
    demand_names = ["Dargom", "Mirzapay", "Akkaradarya", "Miankaltoss", "Narpay", "Karmanakonimex"]
    for name in demand_names:
        raw = load_demand_raw(name)  # m³/s
        daily_m3s = replicate_monthly_to_daily(raw)
        daily = [v * SECONDS_PER_DAY for v in daily_m3s]
        node = system.nodes[name]
        object.__setattr__(node, "requirement", TimeSeries(daily))

    # RF_* nodes: compute runoff m³/month → m³/s → daily — convert m³/s → m³/day
    precip = load_precipitation()  # mm/month
    for rc in load_runoff_config():
        runoff_m3_month = compute_runoff(precip, rc.area, rc.runoff_coefficient)
        runoff_m3s = [v / SECONDS_PER_MONTH for v in runoff_m3_month]
        daily_m3s = replicate_monthly_to_daily(runoff_m3s)
        daily = [v * SECONDS_PER_DAY for v in daily_m3s]
        node = system.nodes[rc.name]
        object.__setattr__(node, "inflow", TimeSeries(daily))


def _build_evaporation_loss(node_id: str) -> EvaporationLossRule:
    """Build an EvaporationLossRule with real HV-derived VA table and daily evap rates."""
    import calendar

    from zarafshan_taqsim.data import (
        derive_va_table,
        expand_monthly_to_daily_cycle,
        load_evaporation,
        load_hv_curve,
        monthly_climatology,
    )

    # Map node IDs to reservoir names for HV curve lookup
    reservoir_names = {
        "RES_Kattakurgan": "kattakurgan",
        "RES_Akdarya": "akdarya",
    }
    res_name = reservoir_names.get(node_id)
    if res_name:
        hv_curve = load_hv_curve(res_name)
        va_table = tuple(tuple(p) for p in derive_va_table(hv_curve))
    else:
        va_table = ((0.0, 0.0), (1.0, 1.0))

    # Build 365-day evaporation rate cycle (mm/day)
    monthly_evap_mm = load_evaporation()  # 72 mm/month values

    # Convert mm/month to mm/day for each month
    mm_per_day_monthly: list[float] = []
    for m in range(72):
        year = 2017 + m // 12
        month_num = m % 12 + 1
        days = calendar.monthrange(year, month_num)[1]
        mm_per_day_monthly.append(monthly_evap_mm[m] / days)

    clim_mm_day = monthly_climatology(mm_per_day_monthly)  # 12 mm/day values
    daily_cycle = expand_monthly_to_daily_cycle(clim_mm_day)  # 365 mm/day values

    return EvaporationLossRule(rates=daily_cycle, va_table=va_table)


def _inject_release_policies(
    system: WaterSystem,
    use_evaporation: bool,
) -> None:
    """Set release policies and optional evaporation loss on Storage nodes."""
    for node in system.nodes.values():
        if not isinstance(node, Storage):
            continue

        # Sum outlet reach capacities (m³/day → m³/s for comparison)
        outlet_cap_m3s = 0.0
        for edge in system.edges.values():
            if edge.source == node.id:
                reach = system.nodes.get(edge.target)
                if isinstance(reach, Reach) and reach.capacity is not None:
                    outlet_cap_m3s += reach.capacity / SECONDS_PER_DAY

        # vr in m³/s: 20% of capacity per month
        default_vr = (node.capacity * DEFAULT_RELEASE_FRACTION) / _SECONDS_PER_MONTH
        vr = min(default_vr, outlet_cap_m3s) if outlet_cap_m3s > 0 else default_vr

        release_policy = ZRBReleaseRule(
            vr=(vr,) * 12,
            v1=(node.dead_storage * BUFFER_ZONE_MULTIPLIER,) * 12,
            v2=(node.capacity * CONSERVATION_ZONE_FRACTION,) * 12,
            buffer_coef=(DEFAULT_BUFFER_COEFFICIENT,) * 12,
            flood_coef=(1.0,) * 12,
        )
        object.__setattr__(node, "release_policy", release_policy)

        loss_rule = _build_evaporation_loss(node.id) if use_evaporation else NoLoss()
        object.__setattr__(node, "loss_rule", loss_rule)


def _inject_split_policies(system: WaterSystem) -> None:
    """Set split policies on Splitter nodes derived from topology.

    Policy assignment:
    - Splitters with natural-tagged downstream edges → EFlowSplitPolicy
    - HW_Dargom → PriorityDistribution (Sink_Kashkadarya priority)
    - HW_Confluence → MonthlyDistribution (single target, trivial)
    - Others → MonthlyDistribution with uniform ratios
    """
    # Load raw JSON for node metadata (natural_split_ratios on HW_AkKaraDarya)
    raw_json = json.loads(TOPOLOGY_PATH.read_text())
    node_metadata: dict[str, dict] = {}
    for raw_node in raw_json["nodes"]:
        if "metadata" in raw_node:
            node_metadata[raw_node["id"]] = raw_node["metadata"]

    for node in system.nodes.values():
        if not isinstance(node, Splitter):
            continue

        # Find outgoing edges from this splitter
        outgoing = [e for e in system.edges.values() if e.source == node.id]
        if not outgoing:
            continue

        target_reaches = tuple(e.target for e in outgoing)
        n_targets = len(target_reaches)

        # Identify natural-tagged outgoing edges
        natural_reaches = tuple(e.target for e in outgoing if "natural" in (e.tags or frozenset()))

        policy = _build_split_policy(
            node.id,
            target_reaches,
            natural_reaches,
            n_targets,
            node_metadata,
            system,
        )
        object.__setattr__(node, "split_policy", policy)


def _build_split_policy(
    splitter_id: str,
    target_reaches: tuple[str, ...],
    natural_reaches: tuple[str, ...],
    n_targets: int,
    node_metadata: dict[str, dict],
    system: WaterSystem,
) -> EFlowSplitPolicy | MonthlyDistribution | PriorityDistribution:
    """Build the appropriate split policy for a splitter node."""
    if splitter_id == "HW_Dargom":
        return _build_priority_policy(target_reaches)

    if splitter_id == "HW_Confluence":
        return MonthlyDistribution(
            targets=target_reaches,
            ratios=tuple((1.0,) * n_targets for _ in range(365)),
        )

    if natural_reaches:
        return _build_eflow_policy(
            splitter_id,
            target_reaches,
            natural_reaches,
            node_metadata,
            system,
        )

    # Default: uniform MonthlyDistribution
    uniform = tuple(1.0 / n_targets for _ in range(n_targets))
    return MonthlyDistribution(
        targets=target_reaches,
        ratios=tuple(uniform for _ in range(365)),
    )


def _build_priority_policy(
    target_reaches: tuple[str, ...],
) -> PriorityDistribution:
    """Build PriorityDistribution for HW_Dargom."""
    from zarafshan_taqsim.data import (
        SECONDS_PER_DAY,
        expand_monthly_to_daily_cycle,
        load_min_flow_raw,
        monthly_climatology,
    )

    kashkadarya_reach = next((r for r in target_reaches if "Sink_Kashkadarya" in r), target_reaches[0])
    other_reaches = [r for r in target_reaches if r != kashkadarya_reach]
    n_other = len(other_reaches)

    # Real min-flow data: m³/s → 12-month climatology → m³/day → 365-day cycle
    raw_mf = load_min_flow_raw("kashkadarya")  # 72 m³/s
    clim = monthly_climatology(raw_mf)  # 12 m³/s
    clim_m3day = tuple(v * SECONDS_PER_DAY for v in clim)  # 12 m³/day
    priority_365 = expand_monthly_to_daily_cycle(clim_m3day)  # 365 m³/day

    return PriorityDistribution(
        targets=target_reaches,
        priority_target=kashkadarya_reach,
        priority_amounts=priority_365,
        remainder_ratios=tuple(1.0 / n_other for _ in range(n_other)) if n_other else (),
    )


def _build_eflow_policy(
    splitter_id: str,
    target_reaches: tuple[str, ...],
    natural_reaches: tuple[str, ...],
    node_metadata: dict[str, dict],
    system: WaterSystem,
) -> EFlowSplitPolicy:
    """Build EFlowSplitPolicy for splitters with natural downstream reaches."""
    # Determine natural target sub-ratios
    if splitter_id in node_metadata:
        split_ratios = node_metadata[splitter_id].get("natural_split_ratios", {})
        if split_ratios:
            natural_targets = tuple((r, split_ratios[r]) for r in natural_reaches if r in split_ratios)
        else:
            natural_targets = tuple((r, 1.0 / len(natural_reaches)) for r in natural_reaches)
    else:
        natural_targets = tuple((r, 1.0) for r in natural_reaches)

    # eflow_cap = sum of natural reach capacities (m³/day)
    eflow_cap = sum(
        system.nodes[r].capacity
        for r in natural_reaches
        if isinstance(system.nodes.get(r), Reach) and system.nodes[r].capacity is not None
    )

    # Remainder ratios for non-natural targets (demand-weighted)
    non_natural = [r for r in target_reaches if r not in natural_reaches]
    remainder_ratios = _compute_demand_weighted_ratios(non_natural) if non_natural else ()

    return EFlowSplitPolicy(
        targets=target_reaches,
        natural_targets=natural_targets,
        eflow_fraction=0.2,
        eflow_cap=eflow_cap,
        remainder_ratios=remainder_ratios,
    )


def _inject_routing_models(system: WaterSystem) -> None:
    """Set placeholder routing models on Reach nodes.

    TODO: replace Lag(lag=0) with calibrated lag values per reach.
    """
    placeholder = Lag(lag=0)
    for node in system.nodes.values():
        if not isinstance(node, Reach):
            continue
        object.__setattr__(node, "routing_model", placeholder)
        object.__setattr__(node, "_routing_state", placeholder.initial_state(node))


def _inject_canal_losses(system: WaterSystem) -> None:
    """Apply CanalLossRule to Reach nodes using canal_properties.csv data.

    Matches edges to reaches by edge ID format: "{source}_to_{target}".
    Reaches without canal property data keep NoReachLoss.
    Reaches on natural-tagged edges (river channels) are skipped.
    """
    import calendar

    from zarafshan_taqsim.data import (
        SECONDS_PER_DAY,
        expand_monthly_to_daily_cycle,
        load_canal_properties,
        load_evaporation,
        monthly_climatology,
    )

    canal_props = load_canal_properties()

    # Build 365-day evap cycle for canals (mm/day)
    monthly_evap_mm = load_evaporation()  # 72 mm/month
    mm_per_day_monthly: list[float] = []
    for m in range(72):
        year = 2017 + m // 12
        month_num = m % 12 + 1
        days = calendar.monthrange(year, month_num)[1]
        mm_per_day_monthly.append(monthly_evap_mm[m] / days)
    clim_mm_day = monthly_climatology(mm_per_day_monthly)
    daily_evap_365 = expand_monthly_to_daily_cycle(clim_mm_day)

    # Collect reach IDs on natural-tagged edges (river channels, not canals)
    natural_reach_ids: set[str] = {
        edge.target
        for edge in system.edges.values()
        if "natural" in (edge.tags or frozenset())
        and isinstance(system.nodes.get(edge.target), Reach)
    }

    for edge_id, props in canal_props.items():
        parts = edge_id.split("_to_")
        if len(parts) != 2:
            continue

        reach_id = f"R_{parts[0]}_{parts[1]}"
        node = system.nodes.get(reach_id)
        if not isinstance(node, Reach):
            continue

        if reach_id in natural_reach_ids:
            logger.debug("Skipping canal loss for natural reach %s", reach_id)
            continue

        loss_rule = CanalLossRule.from_presets(
            lining=props["lining"],
            condition=props["condition"],
            canal_length_km=props["length_km"],
            canal_width_m=props["avg_width_m"],
            evap_rates=daily_evap_365,
            seconds_per_timestep=SECONDS_PER_DAY,
        )
        object.__setattr__(node, "loss_rule", loss_rule)


def get_node_counts(system: WaterSystem) -> dict[str, int]:
    """Count nodes by type in the system.

    Args:
        system: The WaterSystem to analyze.

    Returns:
        Dictionary mapping node type names to counts.
    """
    counts: dict[str, int] = {}
    for node in system.nodes.values():
        type_name = type(node).__name__
        counts[type_name] = counts.get(type_name, 0) + 1
    return counts


# Node colors by type for visualization
NODE_COLORS: dict[type, str] = {
    Source: "#3498db",  # Blue
    Storage: "#27ae60",  # Green
    Splitter: "#e67e22",  # Orange
    Demand: "#e74c3c",  # Red
    Reach: "#bdc3c7",  # Light gray
}

NODE_SIZES: dict[type, int] = {
    Source: 800,
    Storage: 1200,
    Splitter: 600,
    Demand: 800,
    Reach: 200,
}


def _get_geographic_positions(system: WaterSystem) -> dict[str, tuple[float, float]]:
    """Extract geographic positions from node locations.

    For nodes without location attributes, assigns reasonable positions
    based on connected nodes.

    Args:
        system: The WaterSystem to extract positions from.

    Returns:
        Dictionary mapping node IDs to (easting, northing) coordinates.
    """
    pos: dict[str, tuple[float, float]] = {}

    # First pass: collect positions from nodes that have them
    for node_id, node in system.nodes.items():
        loc = getattr(node, "location", None)
        if loc:
            # Topology stores UTM coordinates as [northing, easting].
            # Convert to matplotlib's conventional (x=easting, y=northing).
            pos[node_id] = (loc[1], loc[0])

    # Assign positions to nodes without locations based on network topology
    # Source: upstream (east) of HW_Ravatkhoza
    if "Source" not in pos and "HW_Ravatkhoza" in pos:
        hw_pos = pos["HW_Ravatkhoza"]
        pos["Source"] = (hw_pos[0] + 15000, hw_pos[1] + 5000)

    # Sinks: position based on their incoming connections
    for node_id in system.nodes:
        if node_id.startswith("Sink_") and node_id not in pos:
            # Find incoming edges and average their source positions
            incoming_positions = []
            for edge in system.edges.values():
                if edge.target == node_id and edge.source in pos:
                    incoming_positions.append(pos[edge.source])

            if incoming_positions:
                avg_e = sum(p[0] for p in incoming_positions) / len(incoming_positions)  # m (UTM easting)
                avg_n = sum(p[1] for p in incoming_positions) / len(incoming_positions)  # m (UTM northing)
                # Offset slightly downstream (west and south) by 8km and 5km
                pos[node_id] = (avg_e - 8000, avg_n - 5000)  # m (UTM)

    return pos


def visualize_network(
    system: WaterSystem,
    figsize: tuple[float, float] = (20, 16),
    title: str | None = None,
    show_reaches: bool = False,
    vertical_stretch: float = 1.0,
    font_scale: float = 1.0,
    arrow_size: float = 24,
) -> tuple[plt.Figure, plt.Axes]:
    """Visualize the water system network as a directed graph.

    Uses geographic coordinates (UTM easting/northing) from node locations.

    Node colors indicate type:
    - Blue: Source (water inflows)
    - Green: Storage (reservoirs)
    - Orange: Splitter (HydroWorks distribution points)
    - Red: Demand (irrigation districts)
    - Light gray: Reach (river/canal segments)

    Args:
        system: The WaterSystem to visualize.
        figsize: Figure size as (width, height).
        title: Optional custom title.
        show_reaches: If True, show Reach nodes. Default False for cleaner view.
        vertical_stretch: Display-only exaggeration of the north-south axis.
            Uses the real geographic coordinates but stretches the y-axis by
            this factor for readability. ``1.0`` preserves the true aspect.
        font_scale: Multiplier for labels, legend, title, and tick font sizes.
            ``1.0`` keeps the defaults; values above 1 enlarge the text.
        arrow_size: Size of edge arrowheads in matplotlib/networkx units.
            Larger values make flow direction more visible.

    Returns:
        Tuple of (figure, axes) for further customization.
    """
    if vertical_stretch <= 0:
        msg = f"vertical_stretch must be positive, got {vertical_stretch!r}"
        raise ValueError(msg)
    if font_scale <= 0:
        msg = f"font_scale must be positive, got {font_scale!r}"
        raise ValueError(msg)
    if arrow_size <= 0:
        msg = f"arrow_size must be positive, got {arrow_size!r}"
        raise ValueError(msg)

    g = nx.DiGraph()

    hidden_reaches: set[str] = set()

    # Add nodes and collect colors/sizes
    colors = []
    sizes = []
    for node_id, node in system.nodes.items():
        if not show_reaches and isinstance(node, Reach):
            hidden_reaches.add(node_id)
            continue
        g.add_node(node_id)
        node_type = type(node)
        colors.append(NODE_COLORS.get(node_type, "#95a5a6"))
        sizes.append(NODE_SIZES.get(node_type, 500))

    if show_reaches:
        for edge in system.edges.values():
            if edge.source in g.nodes() and edge.target in g.nodes():
                g.add_edge(edge.source, edge.target)
    else:
        outgoing: dict[str, list[str]] = defaultdict(list)
        for edge in system.edges.values():
            outgoing[edge.source].append(edge.target)

        # When Reach nodes are hidden, reconnect visible nodes across
        # the omitted reach chain so the basin topology remains visible.
        collapsed_edges: set[tuple[str, str]] = set()
        for source in g.nodes():
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
                if target in g.nodes() and source != target:
                    collapsed_edges.add((source, target))

        for source, target in collapsed_edges:
            g.add_edge(source, target)

    pos = _get_geographic_positions(system)
    # Filter to nodes in the graph
    pos = {k: v for k, v in pos.items() if k in g.nodes()}
    # Fallback for any missing nodes
    for node_id in g.nodes():
        if node_id not in pos:
            pos[node_id] = (250000, 4420000)  # Center of basin

    # Create figure
    fig, ax = plt.subplots(figsize=figsize)

    # Keep arrowheads outside the node markers so direction remains visible.
    edge_margin = max(int((max(sizes) / 3.14159) ** 0.5) + 4, 18)

    # Draw edges
    edge_kwargs = {
        "ax": ax,
        "edge_color": "#aab7c4",
        "arrows": True,
        "arrowsize": arrow_size,
        "arrowstyle": "-|>",
        "connectionstyle": "arc3,rad=0.05",
        "width": 2.0,
        "alpha": 0.85,
    }
    edge_signature = inspect.signature(nx.draw_networkx_edges)
    if "min_source_margin" in edge_signature.parameters:
        edge_kwargs["min_source_margin"] = edge_margin
    if "min_target_margin" in edge_signature.parameters:
        edge_kwargs["min_target_margin"] = edge_margin

    nx.draw_networkx_edges(g, pos, **edge_kwargs)

    # Draw nodes
    nx.draw_networkx_nodes(
        g,
        pos,
        ax=ax,
        node_color=colors,
        node_size=sizes,
        alpha=0.9,
        edgecolors="white",
        linewidths=2,
    )

    # Create shortened labels
    labels = {}
    for node_id in g.nodes():
        if node_id.startswith("HW_"):
            labels[node_id] = node_id[3:]
        elif node_id.startswith("RES_"):
            labels[node_id] = node_id[4:]
        elif node_id.startswith("RF_"):
            labels[node_id] = f"RF:{node_id[3:7]}"
        elif node_id.startswith("Sink_"):
            labels[node_id] = node_id[5:]
        elif node_id.startswith("R_"):
            labels[node_id] = ""  # Hide reach labels for readability
        else:
            labels[node_id] = node_id

    # Offset labels slightly away from the network centroid so they do not sit
    # directly on top of the node markers and main edge bundle.
    centroid_x = sum(p[0] for p in pos.values()) / len(pos)
    centroid_y = sum(p[1] for p in pos.values()) / len(pos)
    label_offset_pts = 14

    for node_id, label in labels.items():
        if not label:
            continue

        x, y = pos[node_id]
        dx = x - centroid_x
        dy = y - centroid_y
        if dx == 0 and dy == 0:
            offset_x, offset_y = 0.0, label_offset_pts
            ha, va = "center", "bottom"
        else:
            scale = label_offset_pts / (dx * dx + dy * dy) ** 0.5
            offset_x = dx * scale
            offset_y = dy * scale
            if abs(offset_x) < 2:
                ha = "center"
            elif offset_x > 0:
                ha = "left"
            else:
                ha = "right"

            if abs(offset_y) < 2:
                va = "center"
            elif offset_y > 0:
                va = "bottom"
            else:
                va = "top"

        ax.annotate(
            label,
            xy=(x, y),
            xytext=(offset_x, offset_y),
            textcoords="offset points",
            ha=ha,
            va=va,
            fontsize=8 * font_scale,
            fontweight="bold",
            color="black",
            bbox={
                "boxstyle": "round,pad=0.15",
                "facecolor": "white",
                "edgecolor": "none",
                "alpha": 0.78,
            },
        )

    # Add legend
    legend_elements = [
        plt.scatter([], [], c="#3498db", s=100, label="Source (Inflows)"),
        plt.scatter([], [], c="#27ae60", s=120, label="Storage (Reservoirs)"),
        plt.scatter([], [], c="#e67e22", s=80, label="Splitter (HydroWorks)"),
        plt.scatter([], [], c="#e74c3c", s=100, label="Demand (Irrigation)"),
    ]
    if show_reaches:
        legend_elements.append(plt.scatter([], [], c="#bdc3c7", s=40, label="Reach (Segments)"))
    ax.legend(
        handles=legend_elements,
        loc="upper right",
        fontsize=9 * font_scale,
        frameon=True,
        fancybox=True,
        framealpha=0.92,
        edgecolor="#d0d7de",
    )

    # Title and axes
    if title is None:
        n_shown = len(g.nodes())
        title = f"Zarafshan River Basin Network\n({n_shown} nodes shown, {len(system.edges)} edges total)"
    ax.set_title(title, fontsize=14 * font_scale, fontweight="bold")

    ax.set_xlabel("Easting (m)", fontsize=11 * font_scale)
    if vertical_stretch == 1.0:
        ax.set_ylabel("Northing (m)", fontsize=11 * font_scale)
    else:
        ax.set_ylabel(
            f"Northing (m) — display stretched ×{vertical_stretch:g}",
            fontsize=11 * font_scale,
        )
    ax.set_facecolor("#fbfcfd")
    ax.ticklabel_format(style="plain", useOffset=False)
    ax.tick_params(axis="both", labelsize=9 * font_scale)
    ax.grid(True, alpha=0.18, color="#c7d0d9", linewidth=0.8)
    ax.set_aspect(vertical_stretch)

    plt.tight_layout()
    return fig, ax
