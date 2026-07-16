"""Normalized internal models.

Every model carries explicit units in field names, ISO-8601 timestamps, and a
`source` marker so downstream analysis can distinguish recorded facts
(garmin / strava) from locally calculated metrics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

SOURCE_GARMIN = "garmin"

# Rally RS100 measures the left leg only and doubles it. Analysis must never
# infer left/right balance, and small power skew vs. true bilateral power is possible.
SINGLE_SIDED_POWER_NOTE = "single-sided power meter (left-leg doubled); no L/R balance data"


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
    calories_kcal: float | None
    training_load: float | None  # Garmin's activity training load (unitless)
    aerobic_training_effect: float | None  # Garmin scale 0.0–5.0
    anaerobic_training_effect: float | None  # Garmin scale 0.0–5.0
    source: str = SOURCE_GARMIN
    power_note: str | None = None  # set when power data is present

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
