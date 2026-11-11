"""Two more release rules, for the exercises at the end of the rationing lesson.

They are the lesson's rules (`rationing_coursebook.RationingRelease` and `WinterRelease`) with one change each,
which is what exercises 4 and 6 of the coursebook ask the reader to write.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from taqsim import Storage, Strategy
from taqsim.time import Timestep

from zarafshan_taqsim import rationing_coursebook as rc

EARLY_SUMMER = range(6, 9)  # the first three summer months; the last three are late summer
LATE_WINTER_FROM = 4  # the forecast arrives for the last two winter months (months 4 and 5)


@dataclass(frozen=True)
class SeasonalRationing(Strategy):
    """Exercise 4: the rationing rule with two rations, one for early and one for late summer."""

    __params__: ClassVar[tuple[str, ...]] = ("trigger", "ration", "ration_late")
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {
        "trigger": (0.0, rc.CAPACITY_MM3),
        "ration": (0.0, 1.0),
        "ration_late": (0.0, 1.0),
    }

    trigger: float = 0.0
    ration: float = 1.0  # early summer
    ration_late: float = 1.0

    def release(self, node: Storage, inflow: float, t: Timestep) -> float:
        month = t.index % 12  # 0-5 = winter, 6-8 = early summer, 9-11 = late summer
        need = rc.MONTHLY_NEED_MM3[month]
        if month in rc.SUMMER_MONTHS and node.storage < self.trigger:
            need *= self.ration if month in EARLY_SUMMER else self.ration_late
        return min(need, node.storage)


@dataclass(frozen=True)
class LateForecastRelease(rc.WinterRelease):
    """Exercise 6: the winter rule, but the forecast only exists in the last two winter months."""

    def release(self, node: Storage, inflow: float, t: Timestep) -> float:
        month = t.index % 12
        need = rc.MONTHLY_NEED_MM3[month]
        if month in rc.SUMMER_MONTHS:
            if node.storage < self.trigger:
                need *= self.ration
            return min(need, node.storage)
        known = self.forecast[t.index // 12] if self.forecast and month >= LATE_WINTER_FROM else 0.0
        winter_need = rc.WINTER_FIELDS_NEED_MM3[month]
        if node.storage + known < self.winter_trigger:
            winter_need *= self.winter_ration
        return min(need + winter_need, node.storage)
