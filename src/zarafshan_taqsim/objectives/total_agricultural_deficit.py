"""Total agricultural deficit objective."""

from typing import TYPE_CHECKING

from taqsim.node.events import DeficitRecorded
from taqsim.objective import Objective

if TYPE_CHECKING:
    from taqsim.system import WaterSystem


def total_agricultural_deficit(
    demand_ids: list[str],
) -> Objective:
    """Create objective for total agricultural deficit across multiple demands.

    Args:
        demand_ids: List of demand node IDs to aggregate.

    Returns:
        Objective that sums deficits from all specified demand nodes.
        The returned value is in m³ (cumulative volume shortfall).
    """

    def evaluate(system: "WaterSystem") -> float:
        total = 0.0  # m³
        for node_id in demand_ids:
            if node_id not in system.nodes:
                raise ValueError(f"Demand node '{node_id}' not found")
            # Sum of deficit events, each in m³/timestep → total in m³
            total += system.nodes[node_id].trace(DeficitRecorded, field="deficit").sum()
        return total  # m³

    name = "total_agricultural_deficit"
    if len(demand_ids) <= 3:
        name = f"deficit({'+'.join(demand_ids)})"

    return Objective(
        name=name,
        direction="minimize",
        evaluate=evaluate,
    )
