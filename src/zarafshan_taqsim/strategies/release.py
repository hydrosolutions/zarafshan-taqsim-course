"""Release strategies for Zarafshan River Basin reservoirs."""

from dataclasses import dataclass
from typing import ClassVar

from taqsim import Strategy
from taqsim.constraints import Ordered
from taqsim.node import Storage
from taqsim.time import Frequency, Timestep

_SECONDS_PER_TIMESTEP: dict[Frequency, int] = {
    Frequency.DAILY: 86_400,
    Frequency.WEEKLY: 604_800,
    Frequency.MONTHLY: 2_630_016,
    Frequency.YEARLY: 31_557_600,
}


@dataclass(frozen=True)
class PassThroughRelease(Strategy):
    """Release current-timestep inflow without reservoir buffering.

    This policy is intended for counterfactual natural-flow simulations where a
    storage node remains in the network topology but should behave like a
    hydraulic pass-through rather than an operating reservoir.
    """

    def release(self, node: Storage, inflow: float, t: Timestep) -> float:
        """Return the non-negative inflow volume for the current timestep."""
        return max(0.0, inflow)


@dataclass(frozen=True)
class ZRBReleaseRule(Strategy):
    """Storage Level Operating Policy (SLOP) for ZRB reservoirs.

    Implements a rule-curve release policy based on storage level zones:
    - Below dead storage: No release
    - Buffer zone (dead to V1): Reduced release (buffer_coef × Vr)
    - Conservation zone (V1 to V2): Target release (Vr)
    - Flood control zone (above V2): Increased release (Vr + excess)

    All parameters are 12-month cyclical tuples for seasonal variation.

    Note on units:
        - vr is specified in m³/s (flow rate) for intuitive parameterization
        - Internally converted to m³/timestep using the timestep's frequency
        - v1, v2 are in m³ (volumes)
    """

    __params__: ClassVar[tuple[str, ...]] = ("vr", "v1", "v2", "buffer_coef", "flood_coef")
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {
        "vr": (0.0, 500.0),  # Release rate in m³/s
        "v1": (0.0, 1e9),  # Buffer zone top (m³)
        "v2": (0.0, 1e9),  # Conservation zone top (m³)
        "buffer_coef": (0.0, 1.0),  # Reduction factor
        "flood_coef": (0.0, 5.0),  # Flood zone release multiplier
    }
    __constraints__: ClassVar[tuple] = (Ordered(low="v1", high="v2"),)
    __time_varying__: ClassVar[tuple[str, ...]] = ("vr", "v1", "v2", "buffer_coef", "flood_coef")
    __cyclical__: ClassVar[tuple[str, ...]] = ("vr", "v1", "v2", "buffer_coef", "flood_coef")
    __cyclical_freq__: ClassVar[dict[str, Frequency]] = {
        "vr": Frequency.MONTHLY,
        "v1": Frequency.MONTHLY,
        "v2": Frequency.MONTHLY,
        "buffer_coef": Frequency.MONTHLY,
        "flood_coef": Frequency.MONTHLY,
    }

    vr: tuple[float, ...] = (50.0,) * 12  # Target release rate (m³/s)
    v1: tuple[float, ...] = (100_000_000.0,) * 12  # Buffer zone top, 100 Mm³ (m³)
    v2: tuple[float, ...] = (400_000_000.0,) * 12  # Conservation zone top, 400 Mm³ (m³)
    buffer_coef: tuple[float, ...] = (0.2,) * 12  # Dimensionless reduction factor (0-1)
    flood_coef: tuple[float, ...] = (1.0,) * 12  # Flood zone release multiplier (0-5)

    def release(self, node: Storage, inflow: float, t: Timestep) -> float:
        """Calculate release based on storage level and month.

        Args:
            node: The Storage node.
            inflow: Incoming flow this timestep (m³).
            t: Current timestep (0-indexed).

        Returns:
            Release volume in m³ for this timestep.
        """
        storage = node.storage  # m³
        dead = node.dead_storage  # m³

        # Get monthly parameters via cyclical lookup
        vr_t = self.param_at("vr", t)  # m³/s
        v1_t = self.param_at("v1", t)  # m³
        v2_t = self.param_at("v2", t)  # m³
        buffer_coef_t = self.param_at("buffer_coef", t)
        flood_coef_t = self.param_at("flood_coef", t)

        # No release if at or below dead storage
        if storage <= dead:
            return 0.0  # m³

        available = storage - dead  # m³

        # Convert vr from m³/s to m³/timestep using frequency
        seconds = _SECONDS_PER_TIMESTEP[t.frequency]
        vr_vol = vr_t * seconds  # m³/timestep

        # Determine release based on storage zone
        if storage <= v1_t:
            # Buffer zone: reduced release
            target_release = buffer_coef_t * vr_vol  # m³/timestep
        elif storage <= v2_t:
            # Conservation zone: target release
            target_release = vr_vol  # m³/timestep
        else:
            # Flood control zone: release excess scaled by flood_coef
            excess = storage - v2_t  # m³
            target_release = vr_vol + flood_coef_t * excess  # m³/timestep

        # Cannot release more than available (m³)
        return min(target_release, available)  # m³
