"""Distribution strategies for Zarafshan River Basin splitter nodes."""

from dataclasses import dataclass
from typing import ClassVar

from taqsim import Strategy
from taqsim.node import Splitter
from taqsim.time import Timestep


@dataclass(frozen=True)
class MonthlyDistribution(Strategy):
    """Monthly-varying distribution ratios for Splitter nodes.

    Splits incoming water among targets based on monthly ratios.
    Ratios are normalized to sum to 1.0 for each month.

    Note: This strategy uses a 2D ratios structure (12 months × N targets)
    which is not compatible with standard TaqSim parameter optimization.
    For optimization, use individual ratio parameters instead.
    """

    # Not using __params__ because ratios is a 2D structure
    __params__: ClassVar[tuple[str, ...]] = ()
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {}
    __time_varying__: ClassVar[tuple[str, ...]] = ()
    __cyclical__: ClassVar[tuple[str, ...]] = ()

    # Both fields need defaults to work with frozen dataclass inheritance
    targets: tuple[str, ...] = ()  # Target node IDs
    ratios: tuple[tuple[float, ...], ...] = ()  # 12 months × N targets, dimensionless fractions

    def split(self, node: Splitter, amount: float, t: Timestep) -> dict[str, float]:
        """Split water among targets based on monthly ratios.

        Args:
            node: The Splitter node.
            amount: Total water to split (m³/timestep).
            t: Current timestep (0-indexed).

        Returns:
            Dictionary mapping target IDs to allocated amounts (m³/timestep).
        """
        month = t % len(self.ratios)
        monthly_ratios = self.ratios[month]  # Dimensionless fractions

        # Normalize to ensure sum = 1 (dimensionless)
        total = sum(monthly_ratios)
        if total == 0:
            # Equal distribution if all ratios are zero
            normalized = [1.0 / len(self.targets)] * len(self.targets)  # Dimensionless
        else:
            normalized = [r / total for r in monthly_ratios]  # Dimensionless

        # amount (m³) × ratio (dimensionless) → m³
        return {target: amount * ratio for target, ratio in zip(self.targets, normalized, strict=True)}


@dataclass(frozen=True)
class PriorityDistribution(Strategy):
    """Distribution strategy that serves a priority target first.

    Allocates up to `priority_amount` (m³/timestep) to the priority target
    each timestep, then splits the remainder among the other targets using
    fixed demand-weighted ratios.

    Used at HW_Karmana (Powerplant gets 15 m³/s first) and HW_Dargom
    (Sink_Kashkadarya gets its minimum flow first).
    """

    __params__: ClassVar[tuple[str, ...]] = ()
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {}
    __time_varying__: ClassVar[tuple[str, ...]] = ()
    __cyclical__: ClassVar[tuple[str, ...]] = ()

    targets: tuple[str, ...] = ()
    priority_target: str = ""
    priority_amounts: tuple[float, ...] = ()  # m³/timestep per month (12 values, cyclical)
    remainder_ratios: tuple[float, ...] = ()  # one ratio per non-priority target

    def split(self, node: Splitter, amount: float, t: Timestep) -> dict[str, float]:
        """Split water giving priority target its allocation first.

        Args:
            node: The Splitter node.
            amount: Total water to split (m³/timestep).
            t: Current timestep (0-indexed).

        Returns:
            Dictionary mapping target IDs to allocated amounts (m³/timestep).
        """
        month = t % len(self.priority_amounts)
        priority_need = self.priority_amounts[month]
        priority_alloc = min(amount, priority_need)
        remainder = amount - priority_alloc

        result: dict[str, float] = {self.priority_target: priority_alloc}

        other_targets = [tgt for tgt in self.targets if tgt != self.priority_target]
        if remainder > 0 and other_targets:
            total_ratio = sum(self.remainder_ratios)
            if total_ratio > 0:
                normalized = [r / total_ratio for r in self.remainder_ratios]
            else:
                normalized = [1.0 / len(other_targets)] * len(other_targets)
            for tgt, ratio in zip(other_targets, normalized, strict=True):
                result[tgt] = remainder * ratio
        else:
            for tgt in other_targets:
                result[tgt] = 0.0

        return result
