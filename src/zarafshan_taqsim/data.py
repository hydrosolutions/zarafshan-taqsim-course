"""Data loading utilities for Zarafshan River Basin model.

Unit Conventions
================
This module handles unit conversions between raw data files and the simulation system.

Data File Units (as stored):
- Inflow, demand, min_flow: m³/s (flow rate)
- Precipitation, evaporation: mm (depth)
- Reservoir capacity/storage: m³ (volume)
- Edge capacity: m³/s (flow rate)
- Coordinates: m (UTM easting/northing)
- Area: km² (for runoff calculation)

Simulation Units (after loading):
- All volumes: m³/month (volume per timestep)
- Reservoir capacities: m³
- Efficiencies: dimensionless (0-1)

Conversion Applied:
- Flow rates (m³/s) × SECONDS_PER_MONTH → volumes (m³/month)
"""

import calendar
import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


@dataclass(frozen=True)
class ReservoirConfig:
    """Configuration for a reservoir (storage) node."""

    name: str
    easting: float
    northing: float
    capacity_m3: float
    dead_storage_m3: float
    initial_storage_m3: float
    hv_curve_file: str
    description: str


@dataclass(frozen=True)
class DemandConfig:
    """Configuration for a demand (irrigation district) node."""

    name: str
    easting: float
    northing: float
    field_efficiency: float
    conveyance_efficiency: float
    priority: int


@dataclass(frozen=True)
class HydroworkConfig:
    """Configuration for a HydroWorks (splitter) node."""

    name: str
    easting: float
    northing: float


@dataclass(frozen=True)
class RunoffConfig:
    """Configuration for a runoff source node."""

    name: str
    easting: float
    northing: float
    area: float
    runoff_coefficient: float


@dataclass(frozen=True)
class PassthroughConfig:
    """Configuration for a passthrough node."""

    name: str
    easting: float
    northing: float
    capacity: float
    min_flow: float
    description: str


# Default data directory relative to project root
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "ZRB_baseline"

# Conversion factor: seconds per average month (30.44 days × 24 hours × 3600 seconds)
SECONDS_PER_MONTH = 30.44 * 24 * 3600  # ≈ 2,630,016 s/month

# Conversion factor: seconds per day
SECONDS_PER_DAY = 86_400


def load_inflow(data_dir: Path | None = None) -> list[float]:
    """Load Ravatkhoza inflow time series.

    Converts raw flow rates (m³/s) to volumes (m³/month).

    Args:
        data_dir: Data directory path. Defaults to data/ZRB_baseline.

    Returns:
        List of monthly inflow volumes in m³/month (72 months, 2017-2022).
    """
    data_dir = data_dir or DATA_DIR
    path = data_dir / "inflow" / "inflow_ravatkhoza.csv"

    with open(path) as f:
        reader = csv.DictReader(f)
        # Convert flow rate (m³/s) to volume (m³/month)
        return [float(row["Q_m3s"]) * SECONDS_PER_MONTH for row in reader]


def load_demand(district: str, data_dir: Path | None = None) -> list[float]:
    """Load demand time series for a specific irrigation district.

    Converts raw flow rates (m³/s) to volumes (m³/month).

    Args:
        district: District name (Dargom, Mirzapay, Akkaradarya,
                  Miankaltoss, Narpay, Karmanakonimex).
        data_dir: Data directory path. Defaults to data/ZRB_baseline.

    Returns:
        List of monthly demand volumes in m³/month (72 months, 2017-2022).
    """
    data_dir = data_dir or DATA_DIR
    path = data_dir / "demand" / "demand_all_districts_2017-2022_monthly.csv"

    with open(path) as f:
        reader = csv.DictReader(f)
        # Column names have _m3s suffix to indicate m³/s
        # Convert flow rate (m³/s) to volume (m³/month)
        column_name = f"{district}_m3s"
        return [float(row[column_name]) * SECONDS_PER_MONTH for row in reader]


def load_min_flow(sink: str, data_dir: Path | None = None) -> list[float]:
    """Load minimum flow requirements for a sink node.

    Converts raw flow rates (m³/s) to volumes (m³/month).

    Args:
        sink: Sink name (Sink_Navoi, navoi, etc.) - prefix stripped automatically.
        data_dir: Data directory path. Defaults to data/ZRB_baseline.

    Returns:
        List of monthly minimum flow volumes in m³/month (72 months).
    """
    data_dir = data_dir or DATA_DIR
    # Strip "Sink_" prefix if present
    sink_name = sink.lower().removeprefix("sink_")
    path = data_dir / "min_flow" / f"min_flow_{sink_name}.csv"

    with open(path) as f:
        reader = csv.DictReader(f)
        # Convert flow rate (m³/s) to volume (m³/month)
        return [float(row["Q_m3s"]) * SECONDS_PER_MONTH for row in reader]


def load_hv_curve(reservoir: str, data_dir: Path | None = None) -> list[tuple[float, float]]:
    """Load height-volume curve for a reservoir.

    Args:
        reservoir: Reservoir name (kattakurgan or akdarya) - lowercase.
        data_dir: Data directory path. Defaults to data/ZRB_baseline.

    Returns:
        List of (height_m, volume_m3) tuples sorted by height.
        Heights are in meters (m), volumes in cubic meters (m³).
    """
    data_dir = data_dir or DATA_DIR
    path = data_dir / "reservoir" / f"reservoir_{reservoir.lower()}_hv.csv"

    with open(path) as f:
        reader = csv.DictReader(f)
        return [(float(row["h_m"]), float(row["v_m3"])) for row in reader]


def load_precipitation(data_dir: Path | None = None) -> list[float]:
    """Load precipitation time series.

    Args:
        data_dir: Data directory path. Defaults to data/ZRB_baseline.

    Returns:
        List of monthly precipitation values in mm/month (72 months, 2017-2022).
    """
    data_dir = data_dir or DATA_DIR
    path = data_dir / "precipitation" / "precipitation_2017-2022.csv"

    with open(path) as f:
        reader = csv.DictReader(f)
        return [float(row["Precipitation_mm"]) for row in reader]


def load_edges(data_dir: Path | None = None) -> dict[str, list[dict]]:
    """Load edge configuration from JSON.

    Args:
        data_dir: Data directory path. Defaults to data/ZRB_baseline.

    Returns:
        Dictionary mapping source node IDs to lists of edge definitions.
        Each edge definition has:
        - 'target': downstream node ID
        - 'capacity': maximum flow rate in m³/s
        - 'ecological_flow': minimum ecological flow in m³/s
    """
    data_dir = data_dir or DATA_DIR
    path = data_dir / "config" / "edges_config.json"

    with open(path) as f:
        return json.load(f)


def load_canal_properties(data_dir: Path | None = None) -> dict[str, dict]:
    """Load canal properties for edge loss calculations.

    Canal properties define physical characteristics that determine losses
    from seepage, evaporation, and operational inefficiencies.

    Args:
        data_dir: Data directory path. Defaults to data/ZRB_baseline.

    Returns:
        Dictionary mapping edge IDs to property dictionaries with keys:
        - length_km: Canal segment length in kilometers
        - avg_width_m: Average water surface width in meters
        - lining: Lining type (earthen, partial, concrete)
        - condition: Infrastructure condition (good, average, poor)

    Raises:
        FileNotFoundError: If canal_properties.csv does not exist.
        ValueError: If lining or condition values are invalid.
    """
    data_dir = data_dir or DATA_DIR
    path = data_dir / "config" / "canal_properties.csv"

    valid_linings = {"earthen", "partial", "concrete"}
    valid_conditions = {"good", "average", "poor"}

    properties: dict[str, dict] = {}

    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip comment lines (rows where edge_id starts with #)
            edge_id = row["edge_id"].strip()
            if edge_id.startswith("#"):
                continue

            lining = row["lining"].strip().lower()
            condition = row["condition"].strip().lower()

            if lining not in valid_linings:
                msg = f"Invalid lining '{lining}' for edge {edge_id}. Must be one of: {valid_linings}"
                raise ValueError(msg)

            if condition not in valid_conditions:
                msg = f"Invalid condition '{condition}' for edge {edge_id}. Must be one of: {valid_conditions}"
                raise ValueError(msg)

            properties[edge_id] = {
                "length_km": float(row["length_km"]),
                "avg_width_m": float(row["avg_width_m"]),
                "lining": lining,
                "condition": condition,
            }

    return properties


def load_reservoir_config(data_dir: Path | None = None) -> list[ReservoirConfig]:
    """Load reservoir node configuration.

    Args:
        data_dir: Data directory path. Defaults to data/ZRB_baseline.

    Returns:
        List of ReservoirConfig instances.
    """
    data_dir = data_dir or DATA_DIR
    path = data_dir / "config" / "reservoir_nodes_config.csv"

    with open(path) as f:
        reader = csv.DictReader(f)
        configs = []
        for row in reader:
            configs.append(
                ReservoirConfig(
                    name=row["name"],
                    easting=float(row["easting_m"]),
                    northing=float(row["northing_m"]),
                    capacity_m3=float(row["capacity_m3"]),
                    dead_storage_m3=float(row["dead_storage_m3"]),
                    initial_storage_m3=float(row["initial_storage_m3"]),
                    hv_curve_file=row["hv_curve_file"],
                    description=row["description"],
                )
            )
        return configs


def load_demand_config(data_dir: Path | None = None) -> list[DemandConfig]:
    """Load demand node configuration.

    Args:
        data_dir: Data directory path. Defaults to data/ZRB_baseline.

    Returns:
        List of DemandConfig instances.
    """
    data_dir = data_dir or DATA_DIR
    path = data_dir / "config" / "demand_nodes_config.csv"

    with open(path) as f:
        reader = csv.DictReader(f)
        configs = []
        for row in reader:
            configs.append(
                DemandConfig(
                    name=row["name"],
                    easting=float(row["easting_m"]),
                    northing=float(row["northing_m"]),
                    field_efficiency=float(row["field_efficiency"]),
                    conveyance_efficiency=float(row["conveyance_efficiency"]),
                    priority=int(row["priority"]),
                )
            )
        return configs


def load_hydrowork_config(data_dir: Path | None = None) -> list[HydroworkConfig]:
    """Load HydroWorks (splitter) node configuration.

    Args:
        data_dir: Data directory path. Defaults to data/ZRB_baseline.

    Returns:
        List of HydroworkConfig instances.
    """
    data_dir = data_dir or DATA_DIR
    path = data_dir / "config" / "hydrowork_nodes_config.csv"

    with open(path) as f:
        reader = csv.DictReader(f)
        return [
            HydroworkConfig(
                name=row["name"],
                easting=float(row["easting_m"]),
                northing=float(row["northing_m"]),
            )
            for row in reader
        ]


def load_runoff_config(data_dir: Path | None = None) -> list[RunoffConfig]:
    """Load runoff node configuration.

    Args:
        data_dir: Data directory path. Defaults to data/ZRB_baseline.

    Returns:
        List of RunoffConfig instances.
    """
    data_dir = data_dir or DATA_DIR
    path = data_dir / "config" / "runoff_nodes_config.csv"

    with open(path) as f:
        reader = csv.DictReader(f)
        return [
            RunoffConfig(
                name=row["name"],
                easting=float(row["easting_m"]),
                northing=float(row["northing_m"]),
                area=float(row["area_km2"]),
                runoff_coefficient=float(row["runoff_coefficient"]),
            )
            for row in reader
        ]


def load_passthrough_config(data_dir: Path | None = None) -> list[PassthroughConfig]:
    """Load passthrough node configuration.

    Args:
        data_dir: Data directory path. Defaults to data/ZRB_baseline.

    Returns:
        List of PassthroughConfig instances.
    """
    data_dir = data_dir or DATA_DIR
    path = data_dir / "config" / "passthrough_nodes_config.csv"

    with open(path) as f:
        reader = csv.DictReader(f)
        return [
            PassthroughConfig(
                name=row["name"],
                easting=float(row["easting_m"]),
                northing=float(row["northing_m"]),
                capacity=float(row["capacity_m3s"]),
                min_flow=float(row["min_flow_m3s"]),
                description=row["description"],
            )
            for row in reader
        ]


def load_evaporation(data_dir: Path | None = None) -> list[float]:
    """Load reservoir evaporation rates.

    Args:
        data_dir: Data directory path. Defaults to data/ZRB_baseline.

    Returns:
        List of monthly evaporation depths in mm/month (72 months, 2017-2022).
    """
    data_dir = data_dir or DATA_DIR
    path = data_dir / "reservoir" / "reservoir_evaporation.csv"

    with open(path) as f:
        reader = csv.DictReader(f)
        return [float(row["Evaporation_mm"]) for row in reader]


def derive_va_table(hv_curve: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Derive volume-area lookup table from a height-volume curve.

    Computes surface area for each segment as A = dV/dh (finite differences),
    then returns (volume, area) pairs for interpolation. The first point is
    always (0.0, 0.0) — an empty reservoir has zero surface area.

    Args:
        hv_curve: List of (height_m, volume_m3) tuples, sorted by height.
            Must have at least 2 points.

    Returns:
        List of (volume_m3, area_m2) tuples sorted by volume.

    Raises:
        ValueError: If hv_curve has fewer than 2 points.
    """
    if len(hv_curve) < 2:
        raise ValueError(f"H-V curve must have at least 2 points, got {len(hv_curve)}")

    va_table: list[tuple[float, float]] = [(0.0, 0.0)]

    for i in range(len(hv_curve) - 1):
        h_i, v_i = hv_curve[i]
        h_next, v_next = hv_curve[i + 1]
        dh = h_next - h_i
        dv = v_next - v_i
        area = dv / dh  # m³/m = m²
        midpoint_volume = (v_i + v_next) / 2.0
        va_table.append((midpoint_volume, area))

    return va_table


def load_inflow_daily(
    start_date: str = "2017-01-01",
    end_date: str = "2022-12-31",
    data_dir: Path | None = None,
) -> list[float]:
    """Slice daily inflow CSV and return m3/s values.

    Args:
        start_date: Start date (inclusive) in YYYY-MM-DD format.
        end_date: End date (inclusive) in YYYY-MM-DD format.
        data_dir: Data directory path. Defaults to data/ZRB_baseline.

    Returns:
        List of daily Q_m3s float values within the date range.

    Raises:
        ValueError: If the date range returns 0 rows.
    """
    data_dir = data_dir or DATA_DIR
    path = data_dir / "inflow" / "inflow_ravatkhoza_daily_2010_2023.csv"
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)

    values: list[float] = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_date = date.fromisoformat(row["Date"])
            if start <= row_date <= end:
                values.append(float(row["Q_m3s"]))

    if len(values) == 0:
        msg = f"Date range {start_date} to {end_date} returned 0 rows"
        raise ValueError(msg)

    return values


def replicate_monthly_to_daily(monthly_values: list[float], start_year: int = 2017) -> list[float]:
    """Repeat each monthly value for every day in that month.

    For rate quantities (m3/s) that stay constant within a month.

    Args:
        monthly_values: List of monthly values (must be a multiple of 12).
        start_year: First year of the series.

    Returns:
        List of daily values.

    Raises:
        ValueError: If len(monthly_values) is not a multiple of 12.
    """
    if len(monthly_values) % 12 != 0:
        msg = f"Length must be a multiple of 12, got {len(monthly_values)}"
        raise ValueError(msg)

    daily: list[float] = []
    for i, val in enumerate(monthly_values):
        year = start_year + i // 12
        month = i % 12 + 1
        days = calendar.monthrange(year, month)[1]
        daily.extend([val] * days)
    return daily


def disaggregate_monthly_to_daily(monthly_values: list[float], start_year: int = 2017) -> list[float]:
    """Divide each monthly value by days-in-month.

    For volume/depth quantities (m3/month -> m3/day, mm/month -> mm/day).
    Preserves monthly totals.

    Args:
        monthly_values: List of monthly values (must be a multiple of 12).
        start_year: First year of the series.

    Returns:
        List of daily values.

    Raises:
        ValueError: If len(monthly_values) is not a multiple of 12.
    """
    if len(monthly_values) % 12 != 0:
        msg = f"Length must be a multiple of 12, got {len(monthly_values)}"
        raise ValueError(msg)

    daily: list[float] = []
    for i, val in enumerate(monthly_values):
        year = start_year + i // 12
        month = i % 12 + 1
        days = calendar.monthrange(year, month)[1]
        daily_val = val / days
        daily.extend([daily_val] * days)
    return daily


def monthly_climatology(monthly_values: list[float]) -> tuple[float, ...]:
    """Average N x 12 months down to 12-month climatology.

    Args:
        monthly_values: List of monthly values whose length is a multiple of 12.

    Returns:
        Tuple of 12 values, one per calendar month.
    """
    n_years = len(monthly_values) // 12
    result: list[float] = []
    for m in range(12):
        vals = [monthly_values[y * 12 + m] for y in range(n_years)]
        result.append(sum(vals) / len(vals))
    return tuple(result)


def expand_monthly_to_daily_cycle(
    monthly_12: tuple[float, ...] | list[float],
) -> tuple[float, ...]:
    """12 monthly values -> 365 daily values (day-of-year -> month mapping).

    Maps each day of a non-leap year to its month. Day 0 = Jan 1, Day 31 = Feb 1, etc.
    Used for cyclical strategy indexing via t % 365.

    Args:
        monthly_12: Tuple or list of 12 monthly values.

    Returns:
        Tuple of 365 daily values.
    """
    daily: list[float] = []
    for month in range(1, 13):
        days = calendar.monthrange(2017, month)[1]  # non-leap year
        daily.extend([monthly_12[month - 1]] * days)
    return tuple(daily)


def expand_monthly_ratios_to_daily(
    monthly_ratios: tuple[tuple[float, ...], ...],
) -> tuple[tuple[float, ...], ...]:
    """12 ratio-tuples -> 365 ratio-tuples.

    Each input tuple has N ratios for N targets. Output repeats each month's
    ratios for every day in that month (non-leap year).

    Args:
        monthly_ratios: Tuple of 12 ratio-tuples.

    Returns:
        Tuple of 365 ratio-tuples.
    """
    daily: list[tuple[float, ...]] = []
    for month in range(1, 13):
        days = calendar.monthrange(2017, month)[1]
        daily.extend([monthly_ratios[month - 1]] * days)
    return tuple(daily)


def compute_runoff(precipitation_mm: list[float], area_km2: float, runoff_coeff: float) -> list[float]:
    """Compute runoff volumes from precipitation.

    Formula: runoff_m3 = precip_mm * 0.001 * area_km2 * 1e6 * runoff_coeff
    (i.e., 1mm on 1km2 = 1000 m3)

    Args:
        precipitation_mm: List of precipitation values in mm.
        area_km2: Catchment area in km2.
        runoff_coeff: Runoff coefficient (0-1).

    Returns:
        List of runoff volumes in m3 (same length as precipitation_mm).
    """
    factor = 0.001 * area_km2 * 1e6 * runoff_coeff
    return [p * factor for p in precipitation_mm]


def load_inflow_raw(data_dir: Path | None = None) -> list[float]:
    """Load monthly inflow as raw m3/s (no SECONDS_PER_MONTH multiplication)."""
    data_dir = data_dir or DATA_DIR
    path = data_dir / "inflow" / "inflow_ravatkhoza.csv"
    with open(path) as f:
        reader = csv.DictReader(f)
        return [float(row["Q_m3s"]) for row in reader]


def load_demand_raw(district: str, data_dir: Path | None = None) -> list[float]:
    """Load monthly demand as raw m3/s (no SECONDS_PER_MONTH multiplication)."""
    data_dir = data_dir or DATA_DIR
    path = data_dir / "demand" / "demand_all_districts_2017-2022_monthly.csv"
    with open(path) as f:
        reader = csv.DictReader(f)
        column_name = f"{district}_m3s"
        return [float(row[column_name]) for row in reader]


def load_min_flow_raw(sink: str, data_dir: Path | None = None) -> list[float]:
    """Load monthly min-flow as raw m3/s (no SECONDS_PER_MONTH multiplication)."""
    data_dir = data_dir or DATA_DIR
    sink_name = sink.lower().removeprefix("sink_")
    path = data_dir / "min_flow" / f"min_flow_{sink_name}.csv"
    with open(path) as f:
        reader = csv.DictReader(f)
        return [float(row["Q_m3s"]) for row in reader]


# Default irrigation districts for demand visualization
DEFAULT_DISTRICTS: tuple[str, ...] = (
    "Dargom",
    "Narpay",
    "Akkaradarya",
    "Mirzapay",
    "Miankaltoss",
    "Karmanakonimex",
)

# Color palette for district visualization
DISTRICT_COLORS: dict[str, str] = {
    "Dargom": "#e74c3c",
    "Narpay": "#3498db",
    "Akkaradarya": "#2ecc71",
    "Mirzapay": "#9b59b6",
    "Miankaltoss": "#f39c12",
    "Karmanakonimex": "#1abc9c",
}

TRANSFER_COLORS: dict[str, str] = {
    "Navoi": "#5d6d7e",
    "Jizzakh": "#85929e",
    "Kashkadarya": "#aeb6bf",
}


def plot_supply_demand(
    inflow: list[float] | np.ndarray,
    demands: dict[str, list[float] | np.ndarray] | None = None,
    transfers: dict[str, list[float] | np.ndarray] | None = None,
    runoff: list[float] | np.ndarray | None = None,
    districts: tuple[str, ...] | list[str] | None = None,
    start_year: int = 2017,
    figsize: tuple[float, float] = (14, 10),
    title: str | None = None,
    show_balance: bool = True,
    data_dir: Path | None = None,
) -> tuple[plt.Figure, list[plt.Axes]]:
    """Plot supply (inflow) and demand/obligations visualization for the ZRB system.

    Creates a multi-panel figure showing:
    1. Monthly system inflow (river + optional distributed runoff)
    2. Stacked area chart of obligations (irrigation demand + interbasin transfers)
    3. (Optional) Supply-obligations balance comparison

    Args:
        inflow: Monthly river inflow volumes (m³/month).
        demands: Dictionary mapping district names to demand arrays (m³/month).
            If None with data_dir, loads from files for specified districts.
        transfers: Dictionary mapping sink names to transfer requirement
            arrays (m³/month). Stacked on top of irrigation demand in panel 2.
        runoff: Monthly distributed runoff volumes (m³/month) from precipitation
            source nodes. Stacked on top of river inflow in panel 1.
        districts: District names to include. Defaults to all 6 districts.
        start_year: First year of data for x-axis labels.
        figsize: Figure size as (width, height).
        title: Optional main title for the figure.
        show_balance: If True, show third panel with supply-obligations balance.
        data_dir: Data directory for loading data if not provided directly.

    Returns:
        Tuple of (figure, list of axes) for further customization.
    """
    # Set default districts
    if districts is None:
        districts = DEFAULT_DISTRICTS
    districts = list(districts)

    # Load data if not provided
    data_dir = data_dir or DATA_DIR
    if demands is None:
        demands = {d: load_demand(d, data_dir) for d in districts}

    # Convert to numpy arrays
    inflow_arr = np.array(inflow)
    demand_arrays = {d: np.array(demands[d]) for d in districts}
    runoff_arr = np.array(runoff) if runoff is not None else None
    transfer_arrays = {k: np.array(v) for k, v in transfers.items()} if transfers else {}

    # Total system inflow (river + runoff)
    total_inflow = inflow_arr + runoff_arr if runoff_arr is not None else inflow_arr

    n_months = len(inflow_arr)
    n_years = n_months // 12

    # Create time axis
    time = np.arange(n_months)
    year_ticks = np.arange(0, n_months, 12)
    year_labels = [str(start_year + i) for i in range(n_years)]

    # Determine number of panels
    n_panels = 3 if show_balance else 2

    # Create figure
    fig, axes = plt.subplots(n_panels, 1, figsize=figsize, sharex=True)
    if n_panels == 1:
        axes = [axes]

    # Panel 1: System inflow (river + optional runoff)
    ax1 = axes[0]
    ax1.fill_between(time, 0, inflow_arr / 1e9, alpha=0.3, color="#3498db", label="River (Ravatkhoza)")
    ax1.plot(time, inflow_arr / 1e9, color="#2980b9", linewidth=1.5)

    if runoff_arr is not None:
        ax1.fill_between(
            time, inflow_arr / 1e9, total_inflow / 1e9, alpha=0.3, color="#85c1e9", label="Distributed runoff"
        )
        ax1.plot(time, total_inflow / 1e9, color="#5dade2", linewidth=1, linestyle="--")

    ax1.set_ylabel("Inflow (billion m³/month)")
    panel1_title = "Monthly System Inflow"
    if runoff_arr is not None:
        panel1_title += " (River + Distributed Runoff)"
    ax1.set_title(panel1_title)
    ax1.grid(True, alpha=0.3)
    if runoff_arr is not None:
        ax1.legend(loc="upper left", fontsize=8)

    # Add annual and monthly mean annotations (for total inflow)
    annual_mean = total_inflow.sum() / n_years / 1e9
    monthly_mean = total_inflow.mean() / 1e9
    ax1.axhline(y=monthly_mean, color="#e74c3c", linestyle="--", alpha=0.7, linewidth=1)
    river_annual = inflow_arr.sum() / n_years / 1e9
    if runoff_arr is not None:
        runoff_annual = runoff_arr.sum() / n_years / 1e9
        annotation = (
            f"River: {river_annual:.2f} Bm³/yr\nRunoff: {runoff_annual:.2f} Bm³/yr\nTotal: {annual_mean:.2f} Bm³/yr"
        )
    else:
        annotation = f"Mean: {monthly_mean:.2f} Bm³/mo\nAnnual: {annual_mean:.2f} Bm³/yr"
    ax1.annotate(
        annotation,
        xy=(0.98, 0.95),
        xycoords="axes fraction",
        ha="right",
        va="top",
        fontsize=9,
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.8},
    )

    # Panel 2: Stacked obligations (irrigation demand + interbasin transfers)
    ax2 = axes[1]
    bottom = np.zeros(n_months)
    for district in districts:
        demand_data = demand_arrays[district] / 1e9
        color = DISTRICT_COLORS.get(district, "#95a5a6")
        ax2.fill_between(time, bottom, bottom + demand_data, alpha=0.7, color=color, label=district)
        bottom += demand_data

    # Stack transfers on top of irrigation demand
    for sink_name, transfer_data in transfer_arrays.items():
        color = TRANSFER_COLORS.get(sink_name, "#95a5a6")
        ax2.fill_between(
            time, bottom, bottom + transfer_data / 1e9, alpha=0.5, color=color, label=f"→ {sink_name}", hatch="//"
        )
        bottom += transfer_data / 1e9

    ax2.set_ylabel("Obligations (billion m³/month)")
    if transfer_arrays:
        ax2.set_title("Monthly Water Obligations (Irrigation + Interbasin Transfers)")
    else:
        ax2.set_title(f"Monthly Irrigation Demand by District ({len(districts)} districts)")
    ax2.legend(loc="upper right", ncol=3, fontsize=7)
    ax2.grid(True, alpha=0.3)

    # Panel 3: Supply-obligations balance (optional)
    if show_balance:
        ax3 = axes[2]
        total_demand = sum(demand_arrays[d] for d in districts)
        total_transfers = sum(transfer_arrays.values()) if transfer_arrays else np.zeros(n_months)
        total_obligations = total_demand + total_transfers
        balance = total_inflow - total_obligations

        # Plot as filled areas (positive=surplus, negative=deficit)
        ax3.fill_between(
            time,
            0,
            np.where(balance >= 0, balance, 0) / 1e9,
            alpha=0.5,
            color="#27ae60",
            label="Surplus",
        )
        ax3.fill_between(
            time,
            0,
            np.where(balance < 0, balance, 0) / 1e9,
            alpha=0.5,
            color="#e74c3c",
            label="Deficit",
        )
        ax3.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
        ax3.set_ylabel("Balance (billion m³/month)")
        balance_label = "Supply–Obligations Balance"
        if transfer_arrays:
            balance_label += " (Inflow − Irrigation − Transfers)"
        else:
            balance_label += " (Inflow − Total Demand)"
        ax3.set_title(balance_label)
        ax3.legend(loc="upper right", fontsize=8)
        ax3.grid(True, alpha=0.3)

        # Add summary statistics
        surplus_months = int(np.sum(balance >= 0))
        deficit_months = int(np.sum(balance < 0))
        obligations_ratio = total_obligations.sum() / total_inflow.sum()
        ax3.annotate(
            f"Surplus: {surplus_months} mo | Deficit: {deficit_months} mo"
            f" | Obligations/Inflow: {obligations_ratio:.0%}",
            xy=(0.02, 0.95),
            xycoords="axes fraction",
            ha="left",
            va="top",
            fontsize=9,
            bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.8},
        )

    # Set x-axis labels on bottom panel
    axes[-1].set_xticks(year_ticks)
    axes[-1].set_xticklabels(year_labels)
    axes[-1].set_xlabel("Year")
    axes[-1].set_xlim(0, n_months - 1)

    # Main title
    if title:
        fig.suptitle(title, fontsize=14, fontweight="bold", y=1.02)

    plt.tight_layout()
    return fig, list(axes)
