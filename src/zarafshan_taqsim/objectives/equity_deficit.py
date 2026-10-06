"""Equity deficit objective (max single-district deficit)."""

from typing import TYPE_CHECKING

from taqsim.node.events import DeficitRecorded
from taqsim.objective import Objective

if TYPE_CHECKING:
    from taqsim.system import WaterSystem


def equity_deficit(
    demand_ids: list[str],
) -> Objective:
    """Create objective for maximum single-district deficit (equity measure).

    Measures the worst-off district's cumulative deficit. Minimizing this
    penalizes solutions that sacrifice one district to benefit others.

    Args:
        demand_ids: List of demand node IDs to compare.

    Returns:
        Objective that returns the maximum per-district cumulative deficit.
        The returned value is in m³ (cumulative volume shortfall of the worst-off district).
    """

    def evaluate(system: "WaterSystem") -> float:
        max_deficit = 0.0  # m³
        for node_id in demand_ids:
            if node_id not in system.nodes:
                raise ValueError(f"Demand node '{node_id}' not found")
            district_deficit = system.nodes[node_id].trace(DeficitRecorded, field="deficit").sum()
            max_deficit = max(max_deficit, district_deficit)
        return max_deficit  # m³

    return Objective(
        name="equity_deficit(max_district)",
        direction="minimize",
        evaluate=evaluate,
    )
