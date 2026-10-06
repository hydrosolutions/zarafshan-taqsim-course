"""Pareto front visualization tools."""

import itertools
import logging

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)


def _extract_score_matrix(solutions: list, obj_names: list[str]) -> np.ndarray:
    """Build (n_solutions, n_obj) array from solution scores.

    Args:
        solutions: List of Solution objects with .scores dict.
        obj_names: Ordered objective names.

    Returns:
        2D numpy array of shape (n_solutions, n_objectives).
    """
    return np.array([[s.scores[name] for name in obj_names] for s in solutions])


def plot_pareto_scatter(
    result: object,
    obj_names: list[str],
    *,
    baseline_scores: dict[str, float] | None = None,
    color_obj: str | None = None,
    scale: float = 1e-6,
) -> go.Figure:
    """Create pairwise scatter plots of Pareto front objectives.

    For 4 objectives: C(4,2) = 6 subplots in a 2x3 grid.

    Args:
        result: OptimizeResult with .solutions attribute.
        obj_names: Ordered list of objective names.
        baseline_scores: Optional baseline values to overlay as red stars.
        color_obj: Objective name to use for color scale. Defaults to last.
        scale: Scaling factor for values (default 1e-6 for Mm3).

    Returns:
        Plotly Figure with pairwise scatter subplots.
    """
    solutions = result.solutions  # type: ignore[attr-defined]
    scores = _extract_score_matrix(solutions, obj_names)
    n_obj = len(obj_names)

    if color_obj is None:
        color_obj = obj_names[-1]
    color_idx = obj_names.index(color_obj)
    color_vals = scores[:, color_idx] * scale

    pairs = list(itertools.combinations(range(n_obj), 2))
    n_pairs = len(pairs)
    n_cols = min(3, n_pairs)
    n_rows = (n_pairs + n_cols - 1) // n_cols

    subplot_titles = [f"{obj_names[i]} vs {obj_names[j]}" for i, j in pairs]
    fig = make_subplots(rows=n_rows, cols=n_cols, subplot_titles=subplot_titles)

    for idx, (i, j) in enumerate(pairs):
        row = idx // n_cols + 1
        col = idx % n_cols + 1
        fig.add_trace(
            go.Scatter(
                x=scores[:, i] * scale,
                y=scores[:, j] * scale,
                mode="markers",
                marker={"color": color_vals, "colorscale": "Viridis", "size": 5},
                name=f"Pair {i}-{j}",
                showlegend=False,
            ),
            row=row,
            col=col,
        )
        fig.update_xaxes(title_text=obj_names[i], row=row, col=col)
        fig.update_yaxes(title_text=obj_names[j], row=row, col=col)

        if baseline_scores is not None:
            fig.add_trace(
                go.Scatter(
                    x=[baseline_scores[obj_names[i]] * scale],
                    y=[baseline_scores[obj_names[j]] * scale],
                    mode="markers",
                    marker={"symbol": "star", "size": 15, "color": "red"},
                    name="Baseline",
                    showlegend=(idx == 0),
                ),
                row=row,
                col=col,
            )

    fig.update_layout(
        height=400 * n_rows,
        title_text="Pareto Front — Pairwise Objectives",
    )
    return fig


def plot_pareto_3d(
    result: object,
    obj_names: list[str],
    *,
    x_obj: str | None = None,
    y_obj: str | None = None,
    z_obj: str | None = None,
    color_obj: str | None = None,
    scale: float = 1e-6,
) -> go.Figure:
    """Create 3D scatter of Pareto front.

    Args:
        result: OptimizeResult with .solutions attribute.
        obj_names: Ordered list of objective names.
        x_obj: X-axis objective. Default: first.
        y_obj: Y-axis objective. Default: second.
        z_obj: Z-axis objective. Default: third.
        color_obj: Color objective. Default: fourth (or last).
        scale: Scaling factor.

    Returns:
        Plotly Figure with 3D scatter.
    """
    solutions = result.solutions  # type: ignore[attr-defined]
    scores = _extract_score_matrix(solutions, obj_names)

    x_name = x_obj or obj_names[0]
    y_name = y_obj or obj_names[1]
    z_name = z_obj or (obj_names[2] if len(obj_names) > 2 else obj_names[0])
    c_name = color_obj or (obj_names[3] if len(obj_names) > 3 else obj_names[-1])

    x_idx, y_idx, z_idx, c_idx = (obj_names.index(n) for n in (x_name, y_name, z_name, c_name))

    fig = go.Figure(
        data=[
            go.Scatter3d(
                x=scores[:, x_idx] * scale,
                y=scores[:, y_idx] * scale,
                z=scores[:, z_idx] * scale,
                mode="markers",
                marker={
                    "size": 4,
                    "color": scores[:, c_idx] * scale,
                    "colorscale": "Viridis",
                    "colorbar": {"title": c_name},
                },
            )
        ]
    )
    fig.update_layout(
        scene={
            "xaxis_title": x_name,
            "yaxis_title": y_name,
            "zaxis_title": z_name,
        },
        title_text="Pareto Front — 3D View",
    )
    return fig


def plot_parallel_coordinates(
    result: object,
    obj_names: list[str],
    *,
    decision_vars: list[str] | None = None,
    color_obj: str | None = None,
    scale: float = 1e-6,
) -> go.Figure:
    """Create parallel coordinates plot of Pareto solutions.

    Args:
        result: OptimizeResult with .solutions attribute.
        obj_names: Ordered list of objective names.
        decision_vars: Optional list of parameter names to include as axes.
        color_obj: Objective name for color scale. Default: first.
        scale: Scaling factor for objective values.

    Returns:
        Plotly Figure with parallel coordinates.
    """
    solutions = result.solutions  # type: ignore[attr-defined]
    scores = _extract_score_matrix(solutions, obj_names)

    c_name = color_obj or obj_names[0]
    c_idx = obj_names.index(c_name)

    dimensions = []
    for i, name in enumerate(obj_names):
        dimensions.append({"label": name, "values": scores[:, i] * scale})

    if decision_vars:
        for var_name in decision_vars:
            vals = [s.parameters.get(var_name, 0.0) for s in solutions]
            dimensions.append({"label": var_name.split(".")[-1], "values": vals})

    fig = go.Figure(
        data=go.Parcoords(
            line={
                "color": scores[:, c_idx] * scale,
                "colorscale": "Viridis",
            },
            dimensions=dimensions,
        )
    )
    fig.update_layout(title_text="Pareto Front — Parallel Coordinates")
    return fig
