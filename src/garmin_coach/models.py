"""Normalized internal models.

Every model carries explicit units in field names, ISO-8601 timestamps, and a
`source` marker so downstream analysis can distinguish recorded facts
(garmin / strava) from locally calculated metrics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

SOURCE_GARMIN = "garmin"

# Meter history: single-sided Rally RS100 (left-leg doubled) until 2026-07-23;
# dual-sided Rally from 2026-07-24. Detection is per-ride: balance fields present
# means dual-sided. The note below is attached only to legacy single-sided rides.
SINGLE_SIDED_POWER_NOTE = "single-sided power meter (left-leg doubled); no L/R balance data"
DUAL_SIDED_SINCE = "2026-07-24"


@dataclass(frozen=True)
class RideSummary:
    """One activity as listed by Garmin Connect, normalized."""

    activity_id: int
    name: str
    activity_type: str
    start_time_local: str | None  # ISO 8601, device-local time
    start_time_utc: str | None  # ISO 8601, UTC
    duration_s: float | None
    moving_duration_s: float | None
    distance_km: float | None
    elevation_gain_m: float | None
    elevation_loss_m: float | None
    avg_speed_kmh: float | None
    max_speed_kmh: float | None
    avg_hr_bpm: float | None
    max_hr_bpm: float | None
    avg_power_w: float | None
    max_power_w: float | None
    normalized_power_w: float | None  # as reported by Garmin, not locally calculated
    avg_cadence_rpm: float | None
    left_balance_pct: float | None  # dual-sided rides only; None = single-sided era
    right_balance_pct: float | None
    calories_kcal: float | None
    training_load: float | None  # Garmin's activity training load (unitless)
    aerobic_training_effect: float | None  # Garmin scale 0.0–5.0
    anaerobic_training_effect: float | None  # Garmin scale 0.0–5.0
    source: str = SOURCE_GARMIN
    power_note: str | None = None  # set when power data is present

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
