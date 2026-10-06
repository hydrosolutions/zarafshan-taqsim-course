"""Release variability objective for reservoir operations."""

from typing import TYPE_CHECKING

from taqsim.node.events import WaterReleased
from taqsim.objective import Objective

if TYPE_CHECKING:
    from taqsim.system import WaterSystem


def release_variability(
    reservoir_id: str,
    timesteps: int,
) -> Objective:
    """Create objective for operational variability of reservoir releases.

    Measures sum of absolute month-to-month changes in release volume.
    Lower values indicate smoother, more operationally realistic policies.

    Args:
        reservoir_id: ID of the storage node.
        timesteps: Number of simulation timesteps.

    Returns:
        Objective that calculates total release variability.
        The returned value is in m³ (cumulative absolute change in releases).
    """

    def evaluate(system: "WaterSystem") -> float:
        if reservoir_id not in system.nodes:
            raise ValueError(f"Reservoir node '{reservoir_id}' not found")

        node = system.nodes[reservoir_id]
        release_trace = node.trace(WaterReleased)

        releases = [release_trace.get(t, 0.0) for t in range(timesteps)]

        total_variability = 0.0  # m³
        for t in range(1, timesteps):
            total_variability += abs(releases[t] - releases[t - 1])

        return total_variability  # m³

    return Objective(
        name=f"{reservoir_id}.release_variability",
        direction="minimize",
        evaluate=evaluate,
    )
