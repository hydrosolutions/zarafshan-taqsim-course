"""Optimization result caching."""

import logging
import pickle
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Use a generic type annotation to avoid hard dep on OptimizeResult at import time
_DEFAULT_PATH = Path("_cache/optimization_result.pkl")


@dataclass(frozen=True)
class OptimizationConfig:
    """Configuration snapshot for reproducibility tracking."""

    pop_size: int
    n_generations: int
    seed: int | None
    n_workers: int
    n_timesteps: int


@dataclass(frozen=True)
class CachedResult:
    """Wrapper around an optimization result with metadata."""

    result: object  # OptimizeResult
    timestamp: str  # ISO 8601
    config: OptimizationConfig
    git_hash: str | None


def _get_git_hash() -> str | None:
    """Get short git hash, or None if not in a repo."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def save_result(
    result: object,
    config: OptimizationConfig,
    path: Path = _DEFAULT_PATH,
) -> Path:
    """Save an optimization result to disk.

    Args:
        result: The OptimizeResult to cache.
        config: Configuration used for the run.
        path: File path to write to.

    Returns:
        The path written to.
    """
    cached = CachedResult(
        result=result,
        timestamp=datetime.now(UTC).isoformat(),
        config=config,
        git_hash=_get_git_hash(),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(cached, f)
    logger.info("Saved optimization result to %s", path)
    return path


def load_result(path: Path = _DEFAULT_PATH) -> CachedResult | None:
    """Load a cached optimization result.

    Args:
        path: File path to read from.

    Returns:
        CachedResult if found and valid, None otherwise.
    """
    if not path.exists():
        logger.info("No cached result at %s", path)
        return None
    try:
        with open(path, "rb") as f:
            obj = pickle.load(f)
        if isinstance(obj, CachedResult):
            return obj
        # Backward compat: bare OptimizeResult
        logger.info("Wrapping bare result in CachedResult")
        return CachedResult(
            result=obj,
            timestamp="unknown",
            config=OptimizationConfig(pop_size=0, n_generations=0, seed=None, n_workers=0, n_timesteps=0),
            git_hash=None,
        )
    except Exception:
        logger.warning("Failed to load cached result from %s", path, exc_info=True)
        return None


def run_or_load(
    run_fn: Callable[[], object],
    config: OptimizationConfig,
    *,
    force: bool = False,
    path: Path = _DEFAULT_PATH,
) -> CachedResult:
    """Load cached result or run optimization and cache.

    Args:
        run_fn: Callable that returns an OptimizeResult.
        config: Configuration for the run.
        force: If True, ignore cache and re-run.
        path: Cache file path.

    Returns:
        CachedResult with the optimization result.
    """
    if not force:
        cached = load_result(path)
        if cached is not None:
            logger.info("Using cached result from %s", cached.timestamp)
            return cached

    logger.info("Running optimization...")
    result = run_fn()
    save_result(result, config, path)
    return load_result(path)  # type: ignore[return-value]
