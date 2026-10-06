"""Convergence diagnostics for NSGA-II optimization."""

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pymoo.indicators.hv import HV

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GenerationRecord:
    """Metrics for a single generation."""

    generation: int
    hypervolume: float
    front_size: int


@dataclass
class ConvergenceHistory:
    """Accumulator for per-generation convergence metrics."""

    records: list[GenerationRecord] = field(default_factory=list)

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"generation": r.generation, "hypervolume": r.hypervolume, "front_size": r.front_size}
                for r in self.records
            ]
        )


def make_convergence_callback(
    ref_point: np.ndarray,
) -> tuple[callable, ConvergenceHistory]:
    """Create a callback that records hypervolume and front size per generation.

    Args:
        ref_point: Reference point for hypervolume (shape: n_objectives,).
            All objective values in the front must be dominated by this point.

    Returns:
        Tuple of (callback_fn, history). The callback has signature
        (NSGA2Result, int) -> bool and always returns False.
    """
    history = ConvergenceHistory()
    hv_indicator = HV(ref_point=ref_point)

    def callback(nsga2_result: object, generation: int) -> bool:
        # Extract rank-0 (Pareto front) objectives
        rank = nsga2_result.rank  # type: ignore[attr-defined]
        objectives = nsga2_result.population.objectives  # type: ignore[attr-defined]

        front_mask = rank == 0
        front_obj = objectives[front_mask]
        front_size = int(front_mask.sum())

        # Compute hypervolume of the front
        if front_size > 0 and front_obj.shape[1] > 0:
            try:
                hv_val = float(hv_indicator(front_obj))
            except Exception:
                hv_val = 0.0
        else:
            hv_val = 0.0

        record = GenerationRecord(
            generation=generation,
            hypervolume=hv_val,
            front_size=front_size,
        )
        history.records.append(record)
        logger.debug("Gen %d: HV=%.4e, front_size=%d", generation, hv_val, front_size)
        return False  # Never stop early

    return callback, history


def plot_convergence(
    history: ConvergenceHistory,
    title: str = "Convergence",
) -> go.Figure:
    """Plot hypervolume and front size over generations.

    Args:
        history: ConvergenceHistory with recorded metrics.
        title: Figure title.

    Returns:
        Two-panel Plotly figure.
    """
    df = history.to_dataframe()

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Hypervolume", "Pareto Front Size"),
    )

    fig.add_trace(
        go.Scatter(
            x=df["generation"],
            y=df["hypervolume"],
            mode="lines",
            name="Hypervolume",
            line={"color": "#3498db"},
        ),
        row=1,
        col=1,
    )
    fig.update_yaxes(title_text="Hypervolume", row=1, col=1)

    fig.add_trace(
        go.Scatter(
            x=df["generation"],
            y=df["front_size"],
            mode="lines",
            name="Front Size",
            line={"color": "#2ecc71"},
        ),
        row=1,
        col=2,
    )
    fig.update_yaxes(title_text="# Solutions", row=1, col=2)

    fig.update_xaxes(title_text="Generation", row=1, col=1)
    fig.update_xaxes(title_text="Generation", row=1, col=2)
    fig.update_layout(title_text=title, showlegend=False, height=400)

    return fig
