"""Optimization runner for Zarafshan River Basin."""

import logging
from collections.abc import Callable

import numpy as np
from taqsim import WaterSystem
from taqsim.objective import Objective
from taqsim.optimization import OptimizeResult, optimize

from zarafshan_taqsim.baseline import build_objectives, compute_baseline, compute_reference_point
from zarafshan_taqsim.cache import OptimizationConfig, run_or_load
from zarafshan_taqsim.convergence import make_convergence_callback
from zarafshan_taqsim.network import N_TIMESTEPS, create_zrb_system

logger = logging.getLogger(__name__)


def run_optimization(
    system: WaterSystem,
    objectives: list[Objective],
    timesteps: int = N_TIMESTEPS,
    *,
    pop_size: int = 120,
    generations: int = 100,
    seed: int = 42,
    n_workers: int = 6,
    verbose: bool = True,
    callback: Callable | None = None,
) -> OptimizeResult:
    """Run NSGA-II optimization on the ZRB system.

    Args:
        system: Validated WaterSystem with tunable parameters.
        objectives: List of objectives to optimize.
        timesteps: Simulation timesteps per evaluation.
        pop_size: NSGA-II population size.
        generations: Number of generations.
        seed: Random seed for reproducibility.
        n_workers: Parallel workers (-1 for all cores).
        verbose: Print progress.
        callback: Per-generation callback.

    Returns:
        OptimizeResult with Pareto-optimal solutions.
    """
    logger.info(
        "Starting optimization: pop=%d, gen=%d, workers=%d, timesteps=%d",
        pop_size,
        generations,
        n_workers,
        timesteps,
    )
    return optimize(
        system,
        objectives,
        timesteps,
        pop_size=pop_size,
        generations=generations,
        seed=seed,
        verbose=verbose,
        callback=callback,
        n_workers=n_workers,
    )


def main(
    *,
    force_rerun: bool = False,
    pop_size: int = 120,
    generations: int = 100,
    seed: int = 42,
    n_workers: int = 6,
    timesteps: int = N_TIMESTEPS,
    verbose: bool = True,
) -> None:
    """Run the full optimization pipeline.

    Steps:
        1. Build system via create_zrb_system()
        2. Build objectives via build_objectives()
        3. Compute baseline scores on default system
        4. Compute reference point (1.5x baseline)
        5. Create convergence callback
        6. Run or load cached optimization
        7. Print summary
    """
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")

    # 1. System
    logger.info("Building ZRB system...")
    system = create_zrb_system()
    system.validate()

    # 2. Objectives
    objectives = build_objectives(timesteps=timesteps)
    obj_names = [o.name for o in objectives]
    logger.info("Objectives: %s", obj_names)

    # 3. Baseline
    logger.info("Computing baseline (simulating default system)...")
    baseline_system = create_zrb_system()
    baseline_system.simulate(timesteps)
    baseline = compute_baseline(baseline_system, objectives)
    for name, val in baseline.items():
        logger.info("  %s = %.4e", name, val)

    # 4. Reference point
    ref_point_dict = compute_reference_point(baseline)
    ref_point = np.array([ref_point_dict[n] for n in obj_names])
    logger.info("Reference point: %s", ref_point)

    # 5. Convergence callback
    callback, history = make_convergence_callback(ref_point)

    # 6. Run or load
    config = OptimizationConfig(
        pop_size=pop_size,
        n_generations=generations,
        seed=seed,
        n_workers=n_workers,
        n_timesteps=timesteps,
    )

    def _run() -> OptimizeResult:
        return run_optimization(
            system,
            objectives,
            timesteps,
            pop_size=pop_size,
            generations=generations,
            seed=seed,
            n_workers=n_workers,
            verbose=verbose,
            callback=callback,
        )

    cached = run_or_load(_run, config, force=force_rerun)
    result = cached.result

    # 7. Summary
    logger.info("Optimization complete: %d Pareto solutions", len(result.solutions))
    if history.records:
        last = history.records[-1]
        logger.info("Final HV=%.4e, front_size=%d", last.hypervolume, last.front_size)


if __name__ == "__main__":
    main()
