from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from taqsim.node.reach import Reach
    from taqsim.time import Timestep


@dataclass(frozen=True)
class Lag:
    lag: int

    def __post_init__(self) -> None:
        if self.lag < 0:
            raise ValueError(f"lag must be non-negative, got {self.lag}")

    def initial_state(self, reach: Reach) -> deque[float]:
        if self.lag == 0:
            return deque(maxlen=0)
        return deque([0.0] * self.lag, maxlen=self.lag)

    def route(self, reach: Reach, inflow: float, state: deque[float], t: Timestep) -> tuple[float, deque[float]]:
        if self.lag == 0:
            return inflow, state
        outflow = state[0]
        state.append(inflow)
        return outflow, state

    def storage(self, state: deque[float]) -> float:
        return sum(state)
