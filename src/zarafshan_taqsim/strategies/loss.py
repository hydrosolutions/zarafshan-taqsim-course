"""Loss rules for Zarafshan River Basin infrastructure.

These are physical models, NOT operational strategies.
They do not inherit from Strategy and their parameters are not optimizable.
"""

from dataclasses import dataclass
from typing import Literal

from taqsim.common import LossReason
from taqsim.node import Reach, Storage
from taqsim.time import Timestep

from zarafshan_taqsim.data import SECONDS_PER_MONTH

# Default evaporation rates for Zarafshan region (mm/month)
# Based on USGS Khorezm study and regional estimates
# Peak values ~210 mm/month in summer (Jun-Aug)
ZRB_DEFAULT_EVAP_RATES: tuple[float, ...] = (
    60.0,  # Jan
    70.0,  # Feb
    120.0,  # Mar
    160.0,  # Apr
    200.0,  # May
    210.0,  # Jun (peak, USGS measured)
    210.0,  # Jul (peak, USGS measured)
    200.0,  # Aug
    150.0,  # Sep
    100.0,  # Oct
    70.0,  # Nov
    50.0,  # Dec
)

# Seepage coefficients by canal lining type (calibrated for √Q model)
# Original values were ~23× too high, causing >100% system losses.
# Calibrated to achieve ~63% system efficiency (37% total losses) matching
# Uzbekistan reference data. See docs/plans/CANAL_LOSS_RECALIBRATION_PLAN.md
LINING_PRESETS: dict[str, dict[str, float]] = {
    "earthen": {"seepage_coefficient": 0.050},  # Calibrated (was 0.35)
    "partial": {"seepage_coefficient": 0.020},  # Calibrated (was 0.15)
    "concrete": {"seepage_coefficient": 0.003},  # Calibrated (was 0.02)
}

# Operational loss fractions by infrastructure condition
# Reduced 10x from original estimates - literature indicates operational losses
# (spillage, gate leakage) are minor compared to seepage losses.
# See docs/plans/CANAL_LOSS_RECALIBRATION_PLAN.md
CONDITION_PRESETS: dict[str, dict[str, float]] = {
    "good": {"operational_fraction": 0.002},  # 0.2% - well-maintained
    "average": {"operational_fraction": 0.005},  # 0.5% - typical condition
    "poor": {"operational_fraction": 0.012},  # 1.2% - deteriorated
}


@dataclass(frozen=True)
class EvaporationLossRule:
    """Reservoir evaporation loss rule using H-V-derived surface area.

    Computes monthly evaporation as:
        evap_m3 = rate_mm × 0.001 × interpolated_area_m2

    Surface area is interpolated from a volume-area (VA) lookup table
    derived from the reservoir's height-volume curve via derive_va_table().

    This is a physical model, NOT an operational strategy.
    It does not inherit from Strategy and its parameters are not optimizable.

    Unit conventions:
        - rates: mm/month (evaporation depth)
        - va_table: (volume_m3, area_m2) pairs
        - output: m³/timestep
    """

    rates: tuple[float, ...]  # Evaporation rates in mm/month
    va_table: tuple[tuple[float, float], ...]  # (volume_m3, area_m2) pairs, sorted by volume

    def calculate(self, node: Storage, t: Timestep) -> dict[LossReason, float]:
        """Calculate evaporation loss based on current storage and surface area.

        Args:
            node: The Storage node (provides current storage via node.storage).
            t: Current timestep (0-indexed). Used to index into rates.

        Returns:
            Dictionary with evaporation loss in m³/timestep, or empty if zero.
        """
        if node.storage <= 0:
            return {}

        rate_mm = self.rates[t % len(self.rates)]  # mm/month
        area_m2 = self._interpolate_area(node.storage)  # m²
        evap_m3 = rate_mm * 0.001 * area_m2  # m³/month

        if evap_m3 <= 0:
            return {}

        return {LossReason("evaporation"): evap_m3}

    def _interpolate_area(self, volume: float) -> float:
        """Interpolate surface area from VA table for a given storage volume.

        Uses piecewise linear interpolation. Clamps to table boundaries:
        volume <= 0 returns 0.0, volume >= max returns last area value.

        Args:
            volume: Current storage volume in m³.

        Returns:
            Interpolated surface area in m².
        """
        if volume <= 0:
            return 0.0

        table = self.va_table
        n = len(table)

        # Beyond table range: clamp to last area
        if volume >= table[n - 1][0]:
            return table[n - 1][1]

        # Binary search for the bracketing segment
        lo, hi = 0, n - 1
        while lo < hi - 1:
            mid = (lo + hi) // 2
            if table[mid][0] <= volume:
                lo = mid
            else:
                hi = mid

        # Linear interpolation between lo and hi
        v_lo, a_lo = table[lo]
        v_hi, a_hi = table[hi]
        dv = v_hi - v_lo
        if dv == 0:
            return a_lo

        frac = (volume - v_lo) / dv
        return a_lo + frac * (a_hi - a_lo)


@dataclass(frozen=True)
class CanalLossRule:
    """Configurable canal transmission loss rule for Reach nodes.

    Combines multiple loss components that can be enabled/disabled
    independently. Implements the ReachLossRule protocol.

    Loss Components:
        - Seepage: Flow-dependent √Q model (scales with wetted perimeter)
        - Evaporation: Monthly rates applied to canal surface area
        - Operational: Constant fraction for spillage/leakage at structures

    Unit Conventions:
        - flow: m³/timestep (input)
        - losses: m³/timestep (output)
        - seepage_coefficient: calibration factor for √Q model (dimensionless)
        - evap_rates: mm/month (12 monthly values)
        - canal_length_km: km
        - canal_width_m: m (average top width)
        - operational_fraction: dimensionless (0-1)

    Evidence Base (Uzbekistan):
        - 75% of canals are earthen/unlined
        - System efficiency ~63% (37% total losses)
        - Concrete lining reduces seepage by 96-99%
        - Summer evaporation ~210 mm/month (USGS Khorezm study)
    """

    # Enable/disable flags for each loss type
    enable_seepage: bool = True
    enable_evaporation: bool = True
    enable_operational: bool = True

    # Seepage parameters (flow-dependent √Q model)
    seepage_coefficient: float = 0.15  # Calibrated for canal type (dimensionless)
    lining_type: Literal["earthen", "partial", "concrete"] = "earthen"

    # Evaporation parameters (reach-specific dimensions)
    evap_rates: tuple[float, ...] = ZRB_DEFAULT_EVAP_RATES  # 12 monthly values (mm/month)
    canal_length_km: float = 1.0  # km
    canal_width_m: float = 10.0  # m (average top width)

    # Operational parameters
    operational_fraction: float = 0.05  # 5% default (dimensionless, 0-1)

    # Timestep duration (seconds) — defaults to monthly for backward compatibility
    seconds_per_timestep: float = SECONDS_PER_MONTH

    def calculate(
        self,
        reach: Reach,
        flow: float,
        t: Timestep,
    ) -> dict[LossReason, float]:
        """Calculate total canal losses.

        Args:
            reach: The Reach node being processed.
            flow: Flow through the edge (m³/timestep).
            t: Current timestep (0-indexed).

        Returns:
            Dictionary mapping LossReason to loss amount (m³/timestep).
            Losses are tracked separately for detailed analysis.
        """
        losses: dict[LossReason, float] = {}

        if flow <= 0:
            return losses  # No flow means no losses

        if self.enable_seepage:
            seepage = self._calc_seepage_sqrt_q(flow)
            if seepage > 0:
                losses[LossReason("seepage")] = seepage  # m³/timestep

        if self.enable_evaporation:
            evaporation = self._calc_evaporation(t)
            if evaporation > 0:
                losses[LossReason("evaporation")] = evaporation  # m³/timestep

        if self.enable_operational:
            operational = self._calc_operational(flow)
            if operational > 0:
                losses[LossReason("operational")] = operational  # m³/timestep

        # Total losses cannot exceed available flow
        total_loss = sum(losses.values())  # m³/timestep
        if total_loss > flow:
            # Scale down proportionally to not exceed flow
            scale_factor = flow / total_loss  # dimensionless
            losses = {reason: loss * scale_factor for reason, loss in losses.items()}

        return losses

    def _calc_seepage_sqrt_q(self, flow: float) -> float:
        """Calculate seepage using flow-dependent √Q model.

        Seepage scales with wetted perimeter, which for trapezoidal
        channels is approximately proportional to √Q.

        Formula: loss = α × √(Q) × length × time
        Where α is the seepage coefficient calibrated per canal type.

        Args:
            flow: Flow in m³/timestep.

        Returns:
            Seepage loss in m³/timestep.
        """
        # Convert flow to m³/s for √Q calculation
        flow_m3s = flow / self.seconds_per_timestep  # m³/s

        if flow_m3s <= 0:
            return 0.0

        # Apply √Q relationship: seepage ∝ √(flow) × length
        # seepage_coefficient is calibrated to give reasonable loss rates
        # Units: coefficient (dimensionless) × √(m³/s) × km → loss_rate
        sqrt_q = flow_m3s**0.5  # √(m³/s)

        # Base seepage rate per km of canal
        # seepage_coefficient represents fraction lost per unit √Q per km
        seepage_rate = self.seepage_coefficient * sqrt_q * self.canal_length_km  # m³/s

        # Convert back to m³/timestep
        seepage_volume = seepage_rate * self.seconds_per_timestep  # m³/timestep

        return seepage_volume

    def _calc_evaporation(self, t: Timestep) -> float:
        """Calculate evaporation loss from canal water surface.

        Formula: loss = evap_rate × surface_area
        Surface area = canal_length × canal_width

        Args:
            t: Current timestep (0-indexed).

        Returns:
            Evaporation loss in m³/timestep.
        """
        month = t % len(self.evap_rates)
        evap_rate_mm = self.evap_rates[month]  # mm/month

        # Calculate canal surface area
        # canal_length_km (km) × 1000 (m/km) × canal_width_m (m) → m²
        surface_area_m2 = self.canal_length_km * 1000 * self.canal_width_m  # m²

        # Convert evaporation depth to volume
        # evap_rate (mm/month) × 0.001 (m/mm) × area (m²) → m³/month
        evap_volume = evap_rate_mm * 0.001 * surface_area_m2  # m³/month

        return evap_volume

    def _calc_operational(self, flow: float) -> float:
        """Calculate operational losses (spillage, leakage at structures).

        Simple constant fraction of flow.

        Args:
            flow: Flow in m³/timestep.

        Returns:
            Operational loss in m³/timestep.
        """
        # flow (m³/timestep) × fraction (dimensionless) → m³/timestep
        return flow * self.operational_fraction

    @classmethod
    def from_presets(
        cls,
        lining: Literal["earthen", "partial", "concrete"] = "earthen",
        condition: Literal["good", "average", "poor"] = "average",
        canal_length_km: float = 1.0,
        canal_width_m: float = 10.0,
        evap_rates: tuple[float, ...] | None = None,
        seconds_per_timestep: float = SECONDS_PER_MONTH,
    ) -> "CanalLossRule":
        """Create CanalLossRule from lining and condition presets.

        Args:
            lining: Canal lining type (earthen, partial, concrete).
            condition: Infrastructure condition (good, average, poor).
            canal_length_km: Canal length in km.
            canal_width_m: Average canal top width in m.
            evap_rates: Optional custom evaporation rates (mm/timestep).
            seconds_per_timestep: Duration of one timestep in seconds.

        Returns:
            Configured CanalLossRule instance.
        """
        seepage_coef = LINING_PRESETS[lining]["seepage_coefficient"]
        operational_frac = CONDITION_PRESETS[condition]["operational_fraction"]

        return cls(
            seepage_coefficient=seepage_coef,
            lining_type=lining,
            operational_fraction=operational_frac,
            canal_length_km=canal_length_km,
            canal_width_m=canal_width_m,
            evap_rates=evap_rates or ZRB_DEFAULT_EVAP_RATES,
            seconds_per_timestep=seconds_per_timestep,
        )
