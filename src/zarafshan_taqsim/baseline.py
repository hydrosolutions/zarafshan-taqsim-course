"""Baseline objective values and reference point computation."""

import logging

from taqsim import WaterSystem
from taqsim.objective import Objective

from zarafshan_taqsim.data import DEFAULT_DISTRICTS
from zarafshan_taqsim.network import N_TIMESTEPS
from zarafshan_taqsim.objectives import (
    equity_deficit,
    passthrough_min_flow_deficit,
    release_variability,
    total_agricultural_deficit,
)

logger = logging.getLogger(__name__)

SECONDS_PER_DAY = 86_400


def build_objectives(timesteps: int = N_TIMESTEPS) -> list[Objective]:
    """Construct the 4 ZRB optimization objectives.

    Args:
        timesteps: Number of simulation timesteps (daily).

    Returns:
        List of 4 Objective instances, all minimize direction.
    """
    return [
        total_agricultural_deficit(list(DEFAULT_DISTRICTS)),
        passthrough_min_flow_deficit("Powerplant", min_flow=15.0 * SECONDS_PER_DAY, timesteps=timesteps),
        equity_deficit(list(DEFAULT_DISTRICTS)),
        release_variability("RES_Kattakurgan", timesteps=timesteps),
    ]


def compute_baseline(
    system: WaterSystem,
    objectives: list[Objective],
    timesteps: int = N_TIMESTEPS,
) -> dict[str, float]:
    """Evaluate objectives on an already-simulated system.

    Args:
        system: A WaterSystem that has been simulated.
        objectives: List of objectives to evaluate.
        timesteps: Number of timesteps (used for logging only).

    Returns:
        Dict mapping objective name to its baseline score.
    """
    scores: dict[str, float] = {}
    for obj in objectives:
        val = obj.evaluate(system)
        scores[obj.name] = val
        logger.info("Baseline %s = %.2e", obj.name, val)
    return scores


def compute_reference_point(
    baseline: dict[str, float],
    factor: float = 1.5,
) -> dict[str, float]:
    """Scale baseline values to create a hypervolume reference point.

    Args:
        baseline: Dict of objective name to baseline value.
        factor: Multiplier applied to each baseline value.

    Returns:
        Dict with same keys, values scaled by factor.
    """
    return {name: val * factor for name, val in baseline.items()}
