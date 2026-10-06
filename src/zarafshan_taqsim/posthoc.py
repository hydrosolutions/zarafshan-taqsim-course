"""Post-hoc analysis of optimization results."""

import logging
from dataclasses import dataclass

import numpy as np
import plotly.graph_objects as go

from zarafshan_taqsim.analysis import WaterBalance, compute_water_balance

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Analysis of a single Pareto solution."""

    label: str
    solution_index: int
    scores: dict[str, float]
    parameters: dict[str, float]
    system: object  # WaterSystem
    water_balance: WaterBalance


def extract_representatives(
    result: object,
    obj_names: list[str],
) -> dict[str, int]:
    """Select representative solutions from the Pareto front.

    Picks 4 extreme solutions (argmin per objective) and 1 balanced
    solution (closest to ideal point in normalized space).

    Args:
        result: OptimizeResult with .solutions.
        obj_names: Ordered objective names.

    Returns:
        Dict mapping label to solution index.
    """
    solutions = result.solutions  # type: ignore[attr-defined]
    scores = np.array([[s.scores[name] for name in obj_names] for s in solutions])

    reps: dict[str, int] = {}

    # Extremes: argmin per objective
    for i, name in enumerate(obj_names):
        idx = int(np.argmin(scores[:, i]))
        label = f"Min {name}"
        reps[label] = idx

    # Balanced: closest to ideal in normalized [0,1] space
    mins = scores.min(axis=0)
    maxs = scores.max(axis=0)
    ranges = maxs - mins
    # Avoid division by zero
    ranges = np.where(ranges == 0, 1.0, ranges)
    normalized = (scores - mins) / ranges
    # Distance to origin (ideal = all zeros for minimize)
    distances = np.linalg.norm(normalized, axis=1)
    reps["Balanced"] = int(np.argmin(distances))

    return reps


def analyze_solution(
    solution: object,
    timesteps: int,
    *,
    label: str = "",
    index: int = 0,
) -> AnalysisResult:
    """Simulate and analyze a single Pareto solution.

    Args:
        solution: A Solution object with .to_system(), .scores, .parameters.
        timesteps: Number of timesteps to simulate.
        label: Human-readable label.
        index: Solution index in the result.

    Returns:
        AnalysisResult with simulated system and water balance.
    """
    system = solution.to_system()  # type: ignore[attr-defined]
    system.simulate(timesteps)
    wb = compute_water_balance(system, timesteps=timesteps)
    return AnalysisResult(
        label=label,
        solution_index=index,
        scores=solution.scores,  # type: ignore[attr-defined]
        parameters=solution.parameters,  # type: ignore[attr-defined]
        system=system,
        water_balance=wb,
    )


def analyze_representatives(
    result: object,
    representatives: dict[str, int],
    timesteps: int,
) -> dict[str, AnalysisResult]:
    """Analyze all representative solutions.

    Args:
        result: OptimizeResult.
        representatives: Dict mapping label to solution index.
        timesteps: Number of simulation timesteps.

    Returns:
        Dict mapping label to AnalysisResult.
    """
    solutions = result.solutions  # type: ignore[attr-defined]
    analyses: dict[str, AnalysisResult] = {}
    for label, idx in representatives.items():
        logger.info("Analyzing %s (solution %d)...", label, idx)
        analyses[label] = analyze_solution(solutions[idx], timesteps, label=label, index=idx)
    return analyses


def plot_parameter_profiles(
    analyses: dict[str, AnalysisResult],
    param_bounds: dict[str, tuple[float, float]],
) -> go.Figure:
    """Plot normalized parameter profiles for representative solutions.

    Each representative is a line showing its parameter values normalized
    to [0,1] using the provided bounds.

    Args:
        analyses: Dict of label to AnalysisResult.
        param_bounds: Dict mapping parameter name to (lower, upper).

    Returns:
        Plotly Figure with normalized parameter profiles.
    """
    param_names = list(param_bounds.keys())
    fig = go.Figure()

    for label, analysis in analyses.items():
        normalized = []
        for name in param_names:
            val = analysis.parameters.get(name, 0.0)
            lo, hi = param_bounds[name]
            span = hi - lo
            normalized.append((val - lo) / span if span > 0 else 0.5)

        fig.add_trace(
            go.Scatter(
                x=param_names,
                y=normalized,
                mode="lines+markers",
                name=label,
            )
        )

    fig.update_layout(
        title_text="Parameter Profiles (Normalized)",
        xaxis_title="Parameter",
        yaxis_title="Normalized Value [0, 1]",
        yaxis_range=[0, 1],
    )
    return fig


def print_representative_table(
    analyses: dict[str, AnalysisResult],
    obj_names: list[str],
    *,
    scale: float = 1e6,
    unit: str = "Mm³",
) -> None:
    """Print a comparison table of representative solutions.

    Args:
        analyses: Dict of label to AnalysisResult.
        obj_names: Objective names to display.
        scale: Divisor for raw values. Default 1e6 for Mm³.
        unit: Unit label for display.
    """
    labels = list(analyses.keys())
    header = f"{'Solution':<20}" + "".join(f"{name:>20}" for name in obj_names)
    print(header)
    print("-" * len(header))
    for label in labels:
        a = analyses[label]
        vals = "".join(f"{a.scores.get(n, 0.0) / scale:>18.1f} {unit}" for n in obj_names)
        print(f"{label:<20}{vals}")
