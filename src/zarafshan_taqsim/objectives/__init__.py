"""Zarafshan objective functions package."""

from zarafshan_taqsim.objectives.equity_deficit import equity_deficit
from zarafshan_taqsim.objectives.passthrough_min_flow_deficit import passthrough_min_flow_deficit
from zarafshan_taqsim.objectives.release_variability import release_variability
from zarafshan_taqsim.objectives.total_agricultural_deficit import total_agricultural_deficit

__all__ = [
    "equity_deficit",
    "passthrough_min_flow_deficit",
    "release_variability",
    "total_agricultural_deficit",
]
