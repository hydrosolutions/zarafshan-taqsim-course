"""Power plant cooling / passthrough minimum flow deficit objective."""

from typing import TYPE_CHECKING

from taqsim.node.events import WaterPassedThrough
from taqsim.objective import Objective

if TYPE_CHECKING:
    from taqsim.system import WaterSystem


def passthrough_min_flow_deficit(
    node_id: str,
    min_flow: float,
    timesteps: int,
) -> Objective:
    """Create objective for minimum flow deficit at a PassThrough node.

    Compares actual flow through the node against a required minimum,
    summing up any shortfalls. Useful for ensuring critical infrastructure
    (e.g., power plant cooling) receives adequate water.

    Args:
        node_id: ID of the PassThrough node.
        min_flow: Required minimum flow per timestep (m³/timestep).
        timesteps: Number of simulation timesteps.

    Returns:
        Objective that calculates total minimum flow deficit.
        The returned value is in m³ (cumulative volume shortfall).
    """

    def evaluate(system: "WaterSystem") -> float:
        if node_id not in system.nodes:
            raise ValueError(f"PassThrough node '{node_id}' not found")

        node = system.nodes[node_id]
        passed_trace = node.trace(WaterPassedThrough, field="amount")  # m³/timestep

        total_deficit = 0.0  # m³
        for t in range(timesteps):
            actual = passed_trace.get(t, 0.0)  # m³/timestep
            if actual < min_flow:  # Both in m³/timestep
                total_deficit += min_flow - actual  # m³

        return total_deficit  # m³

    return Objective(
        name=f"{node_id}.min_flow_deficit",
        direction="minimize",
        evaluate=evaluate,
    )
