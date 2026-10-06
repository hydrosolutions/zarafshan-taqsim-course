"""Environmental flow split policy for corridor splitters."""

from dataclasses import dataclass
from typing import ClassVar

from taqsim import Strategy
from taqsim.node import Splitter
from taqsim.time import Timestep


@dataclass(frozen=True)
class EFlowSplitPolicy(Strategy):
    """Environmental flow split policy for corridor splitters.

    Reserves a fraction of inflow for natural downstream targets before
    distributing the remainder among non-natural targets using monthly ratios.

    Supports multiple natural targets with fixed sub-ratios (e.g. a river
    bifurcation where 70% flows to one branch and 30% to another). The
    sub-ratios represent physical geography and are not optimizable.

    The eflow_fraction is the only tunable parameter exposed to the optimizer.
    The eflow_cap provides a physical upper bound on how much water can flow
    through the natural channels (from edge capacity data).

    When eflow_fraction=0, degrades to pure ratio-based split (backwards compatible).
    When eflow_cap is binding, excess goes to the remainder pool.
    """

    __params__: ClassVar[tuple[str, ...]] = ("eflow_fraction",)
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {
        "eflow_fraction": (0.0, 1.0),
    }

    targets: tuple[str, ...]  # ALL downstream target IDs
    natural_targets: tuple[tuple[str, float], ...]  # (target_id, sub_ratio) pairs; ratios sum to 1.0
    eflow_fraction: float = 0.2  # fraction of inflow reserved for e-flow
    eflow_cap: float = float("inf")  # max e-flow volume (m³/timestep), fixed per splitter
    remainder_ratios: tuple[
        tuple[float, ...], ...
    ] = ()  # monthly ratios for non-natural targets (N_months × N_non_natural)

    def split(self, node: Splitter, amount: float, t: Timestep) -> dict[str, float]:
        """Allocate inflow between natural channels and non-natural targets.

        Reserves up to eflow_fraction * amount (capped at eflow_cap) for the
        natural targets, distributed by their sub-ratios. The remainder is
        distributed among non-natural targets using monthly ratio lookup. If
        no ratios are provided, the remainder is split equally.

        Args:
            node: The splitter node initiating the split.
            amount: Total inflow volume (m³/timestep) available to distribute.
            t: Current simulation timestep.

        Returns:
            A dict mapping each target ID to its allocated volume. All targets
            in self.targets are guaranteed to appear as keys.
        """
        # 1. Calculate e-flow allocation
        eflow = min(self.eflow_fraction * amount, self.eflow_cap)

        # 2. Calculate remainder
        remainder = amount - eflow

        # 3. Distribute e-flow among natural targets by sub-ratios
        natural_ids = {nat_id for nat_id, _ in self.natural_targets}
        result: dict[str, float] = {}
        for nat_id, sub_ratio in self.natural_targets:
            result[nat_id] = eflow * sub_ratio

        # 4. Get non-natural targets
        non_natural = [tgt for tgt in self.targets if tgt not in natural_ids]

        # 5. If no non-natural targets, give all water to natural channels
        if not non_natural:
            for nat_id, sub_ratio in self.natural_targets:
                result[nat_id] = amount * sub_ratio
            return result

        if not self.remainder_ratios:
            # Equal split among non-natural targets
            per_target = remainder / len(non_natural)
            for tgt in non_natural:
                result[tgt] = per_target
            return result

        # 6. Select monthly ratios and normalize
        month = t % len(self.remainder_ratios)
        ratios = self.remainder_ratios[month]
        total = sum(ratios)
        normalized = [1.0 / len(non_natural)] * len(non_natural) if total == 0 else [r / total for r in ratios]

        # 7. Build result for non-natural targets
        for tgt, ratio in zip(non_natural, normalized, strict=True):
            result[tgt] = remainder * ratio

        return result
