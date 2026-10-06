"""Custom strategies for Zarafshan River Basin model.

Unit Conventions
================
All strategies in this module work with volumes in m³/month.

- Release rates (vr): Specified in m³/s for intuitive parameterization,
  converted to m³/month internally using SECONDS_PER_MONTH
- Storage thresholds (v1, v2): Specified in m³
- Evaporation rates: Specified in mm/month, converted to m³ using surface area
- Split amounts: m³/month
- Loss amounts: m³/month
"""

from zarafshan_taqsim.strategies.distribution import MonthlyDistribution, PriorityDistribution
from zarafshan_taqsim.strategies.eflow import EFlowSplitPolicy
from zarafshan_taqsim.strategies.loss import (
    CONDITION_PRESETS,
    LINING_PRESETS,
    ZRB_DEFAULT_EVAP_RATES,
    CanalLossRule,
    EvaporationLossRule,
)
from zarafshan_taqsim.strategies.release import PassThroughRelease, ZRBReleaseRule
from zarafshan_taqsim.strategies.routing import Lag

__all__ = [
    "ZRBReleaseRule",
    "PassThroughRelease",
    "MonthlyDistribution",
    "PriorityDistribution",
    "EFlowSplitPolicy",
    "EvaporationLossRule",
    "CanalLossRule",
    "ZRB_DEFAULT_EVAP_RATES",
    "LINING_PRESETS",
    "CONDITION_PRESETS",
    "Lag",
]
