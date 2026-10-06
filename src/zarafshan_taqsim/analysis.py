"""Water balance analysis tools for Zarafshan River Basin model."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from taqsim import Demand, Reach, Sink, Storage, WaterSystem
from taqsim.node.events import DeficitRecorded, WaterGenerated, WaterReceived, WaterSpilled
from taqsim.node.events import WaterConsumed as NodeWaterConsumed
from taqsim.node.events import WaterLost as NodeWaterLost
from taqsim.time import Frequency, Timestep

try:
    from taqsim.edge.events import WaterLost as EdgeWaterLost
except ModuleNotFoundError:
    EdgeWaterLost = None  # Edge events removed in taqsim ≥0.1.4

from zarafshan_taqsim.data import DEFAULT_DISTRICTS


@dataclass
class WaterBalance:
    """Water balance summary for a simulated system.

    All volumes are cumulative totals over the simulation period in m³.
    Fractions are dimensionless (0-1).

    Terminology:
        total_delivered: Gross water arriving at district gates (WaterReceived).
            Includes water that passes through demands to downstream nodes.
            Useful as an operational metric but NOT used in mass balance.
        total_consumed: Net consumptive use by demands (WaterConsumed).
            Only the portion that leaves the hydrological system.
            Used in mass balance closure.
        effective_delivery: Demand-capped delivery — only counts water up to each
            district's requirement per timestep: Σ min(delivered_i_t, demand_i_t).
            Ignores over-delivery that provides no additional benefit.
        effective_efficiency: effective_delivery / total_demand.
            Measures what fraction of total demand is actually satisfied, without
            rewarding over-delivery to individual districts.
        waste_fraction: over_delivery / total_inflow, where over_delivery is
            Σ max(0, delivered_i_t − demand_i_t). Measures the fraction of system
            inflow that is delivered beyond what districts require.
    """

    # Total volumes over simulation period (m³)
    total_inflow: float
    total_delivered: float
    total_consumed: float
    total_deficit: float
    total_losses: float

    # Loss breakdown (m³) — all components sum to total_losses
    reservoir_evaporation_loss: float
    demand_inefficiency_loss: float
    seepage_loss: float
    evaporation_loss: float
    operational_loss: float
    capacity_exceeded_loss: float

    # Mass balance components (m³)
    sink_outflow: float
    reservoir_storage_change: float  # final - initial (positive = net filling)
    closure_error: float

    # Demand-aware volumes (m³)
    total_demand: float  # sum of all district requirements
    effective_delivery: float  # Σ min(delivered_i, demand_i) per district per timestep
    over_delivery: float  # Σ max(0, delivered_i − demand_i)

    # Computed metrics (dimensionless)
    system_efficiency: float  # delivered / inflow
    loss_fraction: float  # total_losses / inflow
    effective_efficiency: float  # effective_delivery / total_demand
    waste_fraction: float  # over_delivery / total_inflow

    # Monthly breakdown (for plotting)
    monthly_inflow: np.ndarray  # shape (n_months,)
    monthly_delivered: np.ndarray  # shape (n_months,)
    monthly_losses: np.ndarray  # shape (n_months,)

    def summary(self) -> str:
        """Return formatted summary of cumulative totals over the simulation period."""
        n = len(self.monthly_inflow)
        lines = [
            f"Water Balance — cumulative total over {n} timesteps",
            "=" * 55,
            "",
            "Inflows:",
            f"  {'River + Runoff:':<24} {self._fmt(self.total_inflow):>12}",
            "",
            "Outflows:",
            f"  {'Consumed by Districts:':<24} {self._fmt(self.total_consumed):>12}  ({self._pct(self.total_consumed)})",
            f"  {'Sink Outflow:':<24} {self._fmt(self.sink_outflow):>12}  ({self._pct(self.sink_outflow)})",
            f"  {'Reservoir ΔStorage:':<24} {self._fmt(self.reservoir_storage_change):>12}  ({self._pct(self.reservoir_storage_change)})",
            "",
            "Losses:",
            f"  {'Reservoir Evaporation:':<24} {self._fmt(self.reservoir_evaporation_loss):>12}  ({self._pct(self.reservoir_evaporation_loss)})",
            f"  {'Demand Inefficiency:':<24} {self._fmt(self.demand_inefficiency_loss):>12}  ({self._pct(self.demand_inefficiency_loss)})",
            f"  {'Canal Seepage:':<24} {self._fmt(self.seepage_loss):>12}  ({self._pct(self.seepage_loss)})",
            f"  {'Canal Evaporation:':<24} {self._fmt(self.evaporation_loss):>12}  ({self._pct(self.evaporation_loss)})",
            f"  {'Canal Operational:':<24} {self._fmt(self.operational_loss):>12}  ({self._pct(self.operational_loss)})",
            f"  {'Edge Overflow:':<24} {self._fmt(self.capacity_exceeded_loss):>12}  ({self._pct(self.capacity_exceeded_loss)})",
            f"  {'Total Losses:':<24} {self._fmt(self.total_losses):>12}  ({self._pct(self.total_losses)})",
            "",
            "Mass Balance Closure:",
            "  Inflow − Consumed − Sinks − Losses − ΔStorage = Error",
            f"  {'Closure Error:':<24} {self._fmt(self.closure_error):>12}  ({self._pct(self.closure_error)})",
            "",
            "Operational Metrics:",
            f"  {'Gross Delivery (gate):':<24} {self._fmt(self.total_delivered):>12}  ({self._pct(self.total_delivered)})",
            f"  {'System Efficiency:':<24} {self.system_efficiency * 100:>11.1f}%",
            f"  {'Unmet Demand:':<24} {self._fmt(self.total_deficit):>12}",
            "",
            "Demand-Aware Metrics:",
            f"  {'Total Demand:':<24} {self._fmt(self.total_demand):>12}",
            f"  {'Effective Delivery:':<24} {self._fmt(self.effective_delivery):>12}",
            f"  {'Over-Delivery:':<24} {self._fmt(self.over_delivery):>12}",
            f"  {'Effective Efficiency:':<24} {self.effective_efficiency * 100:>11.1f}%  (delivery capped at demand)",
            f"  {'Waste Fraction:':<24} {self.waste_fraction * 100:>11.1f}%  (over-delivery / inflow)",
        ]
        return "\n".join(lines)

    def to_dataframe(self) -> pd.DataFrame:
        """Return monthly data as DataFrame."""
        n_months = len(self.monthly_inflow)
        return pd.DataFrame(
            {
                "month": range(1, n_months + 1),
                "inflow_m3": self.monthly_inflow,
                "delivered_m3": self.monthly_delivered,
                "losses_m3": self.monthly_losses,
            }
        )

    def _fmt(self, v: float) -> str:
        """Format volume in appropriate units."""
        if abs(v) >= 1e9:
            return f"{v / 1e9:.2f} Bm³"
        elif abs(v) >= 1e6:
            return f"{v / 1e6:.1f} Mm³"
        else:
            return f"{v:.0f} m³"

    def _pct(self, v: float) -> str:
        """Format as percentage of inflow."""
        if self.total_inflow > 0:
            return f"{v / self.total_inflow * 100:5.1f}%"
        return "  N/A"


def compute_water_balance(
    system: WaterSystem,
    districts: list[str] | None = None,
    timesteps: int | None = None,
) -> WaterBalance:
    """Compute water balance for a simulated system.

    Tracks all water flows through the system and verifies mass balance closure.
    The closure equation is:

        Inflow = Consumed + Sink_outflow + Total_losses + ΔStorage + Error

    Where Total_losses includes canal losses (seepage, evaporation, operational,
    capacity overflow), reservoir evaporation, and demand inefficiency.

    Note: ``total_delivered`` (WaterReceived at demands) is an operational metric
    showing gross water at district gates. It is NOT used in the mass balance
    because demands are pass-through nodes — water flows through them to
    downstream sinks.

    Args:
        system: TaqSim WaterSystem after simulation (must have events).
        districts: List of demand node IDs. Defaults to DEFAULT_DISTRICTS.
        timesteps: Number of timesteps to analyze. Defaults to all available.

    Returns:
        WaterBalance dataclass with computed metrics.

    Raises:
        ValueError: If system has not been simulated (no events).
    """
    if districts is None:
        districts = list(DEFAULT_DISTRICTS)

    # Check system has been simulated
    total_events = sum(len(n.events) for n in system.nodes.values())
    if total_events == 0:
        raise ValueError("System has not been simulated (no events found)")

    # Determine timesteps from system events if not specified
    if timesteps is None:
        max_t = 0
        for node in system.nodes.values():
            if node.events:
                max_t = max(max_t, max(e.t for e in node.events))
        timesteps = max_t + 1

    # Detect system frequency for Timestep construction
    system_freq = getattr(system, "frequency", Frequency.DAILY)
    if not hasattr(system_freq, "value"):
        system_freq = Frequency.DAILY

    # WaterGenerated events are now in m³/timestep (converted at injection time
    # in _inject_timeseries_data), consistent with all other event types.
    per_step_inflow = np.zeros(timesteps)

    # Source node inflow
    for _node_id, node in system.nodes.items():
        gen_trace = node.trace(WaterGenerated)
        if len(gen_trace) == 0:
            continue
        for t in range(timesteps):
            per_step_inflow[t] += gen_trace.get(t, 0.0)

    total_inflow = per_step_inflow.sum()

    # Gross delivery: WaterReceived at demand nodes (operational metric)
    # Also compute demand-capped effective delivery per district per timestep
    per_step_delivered = np.zeros(timesteps)
    total_delivered = 0.0
    total_demand = 0.0
    effective_delivery = 0.0
    over_delivery = 0.0

    for district in districts:
        if district not in system.nodes:
            continue
        node = system.nodes[district]
        delivered_trace = node.trace(WaterReceived)

        for t in range(timesteps):
            delivered_t = delivered_trace.get(t, 0.0)
            # Read demand from node's requirement TimeSeries (frequency-agnostic)
            ts = Timestep(t, frequency=system_freq)
            demand_t = node.requirement[ts] if node.requirement is not None else 0.0
            per_step_delivered[t] += delivered_t
            total_delivered += delivered_t
            total_demand += demand_t
            effective_delivery += min(delivered_t, demand_t)
            over_delivery += max(0.0, delivered_t - demand_t)

    # Net consumptive use: WaterConsumed at demand nodes (for mass balance)
    total_consumed = 0.0
    for node in system.nodes.values():
        if not isinstance(node, Demand):
            continue
        for event in node.events_of_type(NodeWaterConsumed):
            if event.t < timesteps:
                total_consumed += event.amount

    # Deficits
    total_deficit = 0.0
    for district in districts:
        if district not in system.nodes:
            continue
        node = system.nodes[district]
        deficit_trace = node.trace(DeficitRecorded, field="deficit")
        if len(deficit_trace) > 0:
            total_deficit += deficit_trace.sum()

    # Edge losses by type
    edge_loss_totals: dict[str, float] = {}
    per_step_losses = np.zeros(timesteps)
    if EdgeWaterLost is not None:
        for edge in system.edges.values():
            for event in edge.events_of_type(EdgeWaterLost):
                reason = str(event.reason)
                edge_loss_totals[reason] = edge_loss_totals.get(reason, 0.0) + event.amount
                if event.t < timesteps:
                    per_step_losses[event.t] += event.amount

    seepage_loss = edge_loss_totals.get("seepage", 0.0)
    evaporation_loss = edge_loss_totals.get("evaporation", 0.0)
    operational_loss = edge_loss_totals.get("operational", 0.0)
    capacity_exceeded_loss = edge_loss_totals.get("capacity_exceeded", 0.0)

    # Node losses: reservoir evaporation, demand inefficiency, and Reach canal losses
    reservoir_evaporation_loss = 0.0
    demand_inefficiency_loss = 0.0
    for node in system.nodes.values():
        for event in node.events_of_type(NodeWaterLost):
            if event.t >= timesteps:
                continue
            if isinstance(node, Storage):
                reservoir_evaporation_loss += event.amount
            elif isinstance(node, Demand):
                demand_inefficiency_loss += event.amount
            elif isinstance(node, Reach):
                reason = str(event.reason).lower()
                if "seepage" in reason:
                    seepage_loss += event.amount
                elif "evaporation" in reason:
                    evaporation_loss += event.amount
                else:
                    operational_loss += event.amount
            per_step_losses[event.t] += event.amount

    # Reach spillage: water exceeding canal capacity (WaterSpilled on Reach nodes)
    for node in system.nodes.values():
        if not isinstance(node, Reach):
            continue
        for event in node.events_of_type(WaterSpilled):
            if event.t >= timesteps:
                continue
            capacity_exceeded_loss += event.amount
            per_step_losses[event.t] += event.amount

    total_losses = (
        seepage_loss
        + evaporation_loss
        + operational_loss
        + capacity_exceeded_loss
        + reservoir_evaporation_loss
        + demand_inefficiency_loss
    )

    # Sink outflow (water received by terminal Sink nodes)
    sink_outflow = 0.0
    for node in system.nodes.values():
        if not isinstance(node, Sink):
            continue
        received_trace = node.trace(WaterReceived)
        for t in range(timesteps):
            sink_outflow += received_trace.get(t, 0.0)

    # Reservoir storage change (final - initial; positive = net filling)
    reservoir_storage_change = 0.0
    for node in system.nodes.values():
        if not isinstance(node, Storage):
            continue
        reservoir_storage_change += node.storage - node.initial_storage

    # Mass balance closure
    closure_error = total_inflow - total_consumed - sink_outflow - total_losses - reservoir_storage_change

    # Operational metrics
    system_efficiency = total_delivered / total_inflow if total_inflow > 0 else 0.0
    loss_fraction = total_losses / total_inflow if total_inflow > 0 else 0.0
    effective_efficiency = effective_delivery / total_demand if total_demand > 0 else 0.0
    waste_fraction = over_delivery / total_inflow if total_inflow > 0 else 0.0

    return WaterBalance(
        total_inflow=total_inflow,
        total_delivered=total_delivered,
        total_consumed=total_consumed,
        total_deficit=total_deficit,
        total_losses=total_losses,
        reservoir_evaporation_loss=reservoir_evaporation_loss,
        demand_inefficiency_loss=demand_inefficiency_loss,
        seepage_loss=seepage_loss,
        evaporation_loss=evaporation_loss,
        operational_loss=operational_loss,
        capacity_exceeded_loss=capacity_exceeded_loss,
        sink_outflow=sink_outflow,
        reservoir_storage_change=reservoir_storage_change,
        closure_error=closure_error,
        total_demand=total_demand,
        effective_delivery=effective_delivery,
        over_delivery=over_delivery,
        system_efficiency=system_efficiency,
        loss_fraction=loss_fraction,
        effective_efficiency=effective_efficiency,
        waste_fraction=waste_fraction,
        monthly_inflow=per_step_inflow,
        monthly_delivered=per_step_delivered,
        monthly_losses=per_step_losses,
    )
