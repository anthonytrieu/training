"""Convert raw Garmin Connect responses into stable internal models.

Garmin's list responses use slightly different key names across endpoints and
firmware versions, so lookups tolerate known aliases and missing fields become
None rather than guesses.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .models import SINGLE_SIDED_POWER_NOTE, SOURCE_GARMIN, RideSummary


def _num(raw: dict[str, Any], *keys: str) -> float | None:
    """First numeric value found under any of the given keys, else None."""
    for key in keys:
        value = raw.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _iso(timestamp: str | None) -> str | None:
    """Garmin uses 'YYYY-MM-DD HH:MM:SS'; normalize to ISO 8601."""
    if not timestamp or not isinstance(timestamp, str):
        return None
    return timestamp.strip().replace(" ", "T")


def _round(value: float | None, digits: int = 1) -> float | None:
    return None if value is None else round(value, digits)


def _mps_to_kmh(value: float | None) -> float | None:
    return None if value is None else value * 3.6


def normalize_ride_summary(raw: dict[str, Any]) -> RideSummary:
    """Normalize one item from Garmin's activity list into a RideSummary."""
    activity_type = raw.get("activityType") or {}
    type_key = activity_type.get("typeKey") if isinstance(activity_type, dict) else None

    distance_m = _num(raw, "distance")
    avg_power = _num(raw, "avgPower", "averagePower")

    return RideSummary(
        activity_id=int(raw["activityId"]),
        name=str(raw.get("activityName") or "Untitled activity"),
        activity_type=str(type_key or "unknown"),
        start_time_local=_iso(raw.get("startTimeLocal")),
        start_time_utc=_iso(raw.get("startTimeGMT")),
        duration_s=_round(_num(raw, "duration")),
        moving_duration_s=_round(_num(raw, "movingDuration")),
        distance_km=_round(None if distance_m is None else distance_m / 1000, 2),
        elevation_gain_m=_round(_num(raw, "elevationGain")),
        elevation_loss_m=_round(_num(raw, "elevationLoss")),
        avg_speed_kmh=_round(_mps_to_kmh(_num(raw, "averageSpeed"))),
        max_speed_kmh=_round(_mps_to_kmh(_num(raw, "maxSpeed"))),
        avg_hr_bpm=_round(_num(raw, "averageHR", "avgHr")),
        max_hr_bpm=_round(_num(raw, "maxHR", "maxHr")),
        avg_power_w=_round(avg_power),
        max_power_w=_round(_num(raw, "maxPower")),
        normalized_power_w=_round(_num(raw, "normPower", "normalizedPower")),
        avg_cadence_rpm=_round(
            _num(raw, "averageBikingCadenceInRevPerMinute", "avgBikeCadence", "averageCadence")
        ),
        calories_kcal=_round(_num(raw, "calories"), 0),
        training_load=_round(_num(raw, "activityTrainingLoad")),
        aerobic_training_effect=_round(_num(raw, "aerobicTrainingEffect")),
        anaerobic_training_effect=_round(_num(raw, "anaerobicTrainingEffect")),
        power_note=SINGLE_SIDED_POWER_NOTE if avg_power is not None else None,
    )


def normalize_ride_summaries(raw_activities: list[dict[str, Any]]) -> list[RideSummary]:
    return [normalize_ride_summary(a) for a in raw_activities]


# ---------------------------------------------------------------------------
# Detailed activity views (Milestone 3). These return plain dicts with stable,
# unit-suffixed keys — the dict schema is the model. Missing data stays None.
# ---------------------------------------------------------------------------

GARMIN_REPORTED_NOTE = (
    "intensity_factor, training_stress_score and ftp_at_ride_w are Garmin-reported "
    "values based on the FTP configured at ride time, not locally calculated"
)


def _epoch_ms_iso(ms: Any) -> str | None:
    """Epoch milliseconds -> naive ISO string (Garmin gives these in local/GMT pairs)."""
    if not isinstance(ms, (int, float)) or isinstance(ms, bool):
        return None
    return datetime.fromtimestamp(ms / 1000, tz=UTC).replace(tzinfo=None).isoformat()


def normalize_activity_summary(raw: dict[str, Any]) -> dict[str, Any]:
    """Full single-activity view from Garmin's activity-service response."""
    dto: dict[str, Any] = raw.get("summaryDTO") or {}
    type_dto = raw.get("activityTypeDTO") or {}
    distance_m = _num(dto, "distance")
    avg_power = _num(dto, "averagePower")

    return {
        "activity_id": raw.get("activityId"),
        "name": raw.get("activityName") or "Untitled activity",
        "activity_type": type_dto.get("typeKey") or "unknown",
        "location": raw.get("locationName"),
        "start_time_local": _iso(dto.get("startTimeLocal")),
        "start_time_utc": _iso(dto.get("startTimeGMT")),
        "duration_s": _round(_num(dto, "duration")),
        "moving_duration_s": _round(_num(dto, "movingDuration")),
        "elapsed_duration_s": _round(_num(dto, "elapsedDuration")),
        "distance_km": _round(None if distance_m is None else distance_m / 1000, 2),
        "elevation_gain_m": _round(_num(dto, "elevationGain")),
        "elevation_loss_m": _round(_num(dto, "elevationLoss")),
        "avg_speed_kmh": _round(_mps_to_kmh(_num(dto, "averageSpeed"))),
        "avg_moving_speed_kmh": _round(_mps_to_kmh(_num(dto, "averageMovingSpeed"))),
        "max_speed_kmh": _round(_mps_to_kmh(_num(dto, "maxSpeed"))),
        "avg_hr_bpm": _round(_num(dto, "averageHR")),
        "max_hr_bpm": _round(_num(dto, "maxHR")),
        "min_hr_bpm": _round(_num(dto, "minHR")),
        "avg_power_w": _round(avg_power),
        "max_power_w": _round(_num(dto, "maxPower")),
        "normalized_power_w": _round(_num(dto, "normalizedPower")),
        "max_power_20min_w": _round(_num(dto, "maxPowerTwentyMinutes")),
        "ftp_at_ride_w": _round(_num(dto, "functionalThresholdPower")),
        "intensity_factor": _round(_num(dto, "intensityFactor"), 3),
        "training_stress_score": _round(_num(dto, "trainingStressScore")),
        "avg_cadence_rpm": _round(_num(dto, "averageBikeCadence")),
        "max_cadence_rpm": _round(_num(dto, "maxBikeCadence")),
        "calories_kcal": _round(_num(dto, "calories"), 0),
        "training_load": _round(_num(dto, "activityTrainingLoad")),
        "aerobic_training_effect": _round(_num(dto, "trainingEffect")),
        "anaerobic_training_effect": _round(_num(dto, "anaerobicTrainingEffect")),
        "avg_temperature_c": _round(_num(dto, "averageTemperature")),
        "avg_respiration_brpm": _round(_num(dto, "avgRespirationRate")),
        "begin_stamina_pct": _round(_num(dto, "beginPotentialStamina")),
        "end_stamina_pct": _round(_num(dto, "endPotentialStamina")),
        "min_stamina_pct": _round(_num(dto, "minAvailableStamina")),
        "source": SOURCE_GARMIN,
        "power_note": SINGLE_SIDED_POWER_NOTE if avg_power is not None else None,
        "garmin_reported_note": GARMIN_REPORTED_NOTE if avg_power is not None else None,
    }


def normalize_laps(raw: dict[str, Any]) -> dict[str, Any]:
    """Lap/split breakdown from Garmin's lapDTOs."""
    laps = []
    for lap in raw.get("lapDTOs") or []:
        distance_m = _num(lap, "distance")
        laps.append(
            {
                "lap_index": lap.get("lapIndex"),
                "start_time_utc": _iso(lap.get("startTimeGMT")),
                "duration_s": _round(_num(lap, "duration")),
                "moving_duration_s": _round(_num(lap, "movingDuration")),
                "distance_km": _round(None if distance_m is None else distance_m / 1000, 2),
                "elevation_gain_m": _round(_num(lap, "elevationGain")),
                "elevation_loss_m": _round(_num(lap, "elevationLoss")),
                "avg_speed_kmh": _round(_mps_to_kmh(_num(lap, "averageSpeed"))),
                "avg_hr_bpm": _round(_num(lap, "averageHR")),
                "max_hr_bpm": _round(_num(lap, "maxHR")),
                "avg_power_w": _round(_num(lap, "averagePower")),
                "max_power_w": _round(_num(lap, "maxPower")),
                "normalized_power_w": _round(_num(lap, "normalizedPower")),
                "avg_cadence_rpm": _round(_num(lap, "averageBikeCadence")),
                "calories_kcal": _round(_num(lap, "calories"), 0),
            }
        )
    return {
        "activity_id": raw.get("activityId"),
        "lap_count": len(laps),
        "laps": laps,
        "source": SOURCE_GARMIN,
    }


def normalize_zones(raw: list[dict[str, Any]], unit: str) -> dict[str, Any]:
    """Time-in-zone buckets (HR or power). share_pct is calculated locally."""
    total = sum(z.get("secsInZone") or 0.0 for z in raw)
    zones = []
    for z in sorted(raw, key=lambda z: z.get("zoneNumber") or 0):
        secs = _num(z, "secsInZone")
        zones.append(
            {
                "zone": z.get("zoneNumber"),
                f"low_boundary_{unit}": _num(z, "zoneLowBoundary"),
                "time_s": _round(secs),
                "share_pct": _round(100 * secs / total, 1) if secs and total else 0.0,
            }
        )
    return {
        "zones": zones,
        "total_time_s": _round(total),
        "source": SOURCE_GARMIN,
        "note": (
            "zone boundaries come from the user's Garmin settings; "
            "share_pct is calculated locally from Garmin's time-in-zone seconds"
        ),
    }


_SERIES_METRICS = {
    "sumDuration": ("offset_s", 0),
    "sumDistance": ("distance_m", 0),
    "directPower": ("power_w", 0),
    "directHeartRate": ("hr_bpm", 0),
    "directBikeCadence": ("cadence_rpm", 0),
    "directSpeed": ("speed_kmh", 1),
    "directElevation": ("elevation_m", 1),
}


def normalize_time_series(raw: dict[str, Any]) -> dict[str, Any]:
    """Downsampled per-second streams from Garmin's activity details response."""
    descriptors = raw.get("metricDescriptors") or []
    index_of = {
        d["key"]: d["metricsIndex"] for d in descriptors if d.get("key") in _SERIES_METRICS
    }
    points = []
    for row in raw.get("activityDetailMetrics") or []:
        metrics = row.get("metrics") or []
        point: dict[str, Any] = {}
        for key, idx in index_of.items():
            name, digits = _SERIES_METRICS[key]
            value = metrics[idx] if idx < len(metrics) else None
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if key == "directSpeed":
                    value = value * 3.6
                point[name] = round(float(value), digits)
            else:
                point[name] = None
        points.append(point)
    return {
        "activity_id": raw.get("activityId"),
        "point_count": len(points),
        "points": points,
        "source": SOURCE_GARMIN,
        "note": "downsampled by Garmin to ~point_count evenly spaced samples",
    }


def normalize_training_status(raw: dict[str, Any], requested_date: str) -> dict[str, Any]:
    """Training status + acute/chronic load + monthly load balance + VO2 max."""
    status_block = (raw.get("mostRecentTrainingStatus") or {}).get("latestTrainingStatusData") or {}
    # keyed by device id; take the primary training device entry (or the first)
    entries = list(status_block.values())
    primary = next((e for e in entries if e.get("primaryTrainingDevice")), None) or (
        entries[0] if entries else {}
    )
    acute = primary.get("acuteTrainingLoadDTO") or {}

    balance_block = (raw.get("mostRecentTrainingLoadBalance") or {}).get(
        "metricsTrainingLoadBalanceDTOMap"
    ) or {}
    balance_entries = list(balance_block.values())
    balance = next((b for b in balance_entries if b.get("primaryTrainingDevice")), None) or (
        balance_entries[0] if balance_entries else {}
    )

    vo2 = (raw.get("mostRecentVO2Max") or {}).get("cycling") or {}

    return {
        "requested_date": requested_date,
        "status_date": primary.get("calendarDate"),
        "sport": primary.get("sport"),
        "training_status_phrase": primary.get("trainingStatusFeedbackPhrase"),
        "training_paused": primary.get("trainingPaused"),
        "acute_load": _num(acute, "dailyTrainingLoadAcute"),
        "chronic_load": _num(acute, "dailyTrainingLoadChronic"),
        "acwr_ratio": _num(acute, "dailyAcuteChronicWorkloadRatio"),
        "acwr_status": acute.get("acwrStatus"),
        "monthly_load_aerobic_low": _round(_num(balance, "monthlyLoadAerobicLow")),
        "monthly_load_aerobic_low_target_min": _num(balance, "monthlyLoadAerobicLowTargetMin"),
        "monthly_load_aerobic_low_target_max": _num(balance, "monthlyLoadAerobicLowTargetMax"),
        "monthly_load_aerobic_high": _round(_num(balance, "monthlyLoadAerobicHigh")),
        "monthly_load_aerobic_high_target_min": _num(balance, "monthlyLoadAerobicHighTargetMin"),
        "monthly_load_aerobic_high_target_max": _num(balance, "monthlyLoadAerobicHighTargetMax"),
        "monthly_load_anaerobic": _round(_num(balance, "monthlyLoadAnaerobic")),
        "monthly_load_anaerobic_target_min": _num(balance, "monthlyLoadAnaerobicTargetMin"),
        "monthly_load_anaerobic_target_max": _num(balance, "monthlyLoadAnaerobicTargetMax"),
        "load_balance_phrase": balance.get("trainingBalanceFeedbackPhrase"),
        "vo2max_cycling": _num(vo2, "vo2MaxPreciseValue") or _num(vo2, "vo2MaxValue"),
        "source": SOURCE_GARMIN,
    }


def normalize_training_readiness(raw: list[dict[str, Any]], requested_date: str) -> dict[str, Any]:
    """Training readiness entries; empty for device-only accounts (needs a Garmin watch)."""
    if not raw:
        return {
            "requested_date": requested_date,
            "available": False,
            "entries": [],
            "note": (
                "No training readiness data. Garmin computes readiness on watches; "
                "an Edge bike computer alone does not produce it."
            ),
            "source": SOURCE_GARMIN,
        }
    entries = []
    for item in raw:
        entries.append(
            {
                "timestamp_local": _iso(item.get("timestampLocal") or item.get("timestamp")),
                "score": _num(item, "score"),
                "level": item.get("level"),
                "feedback_short": item.get("feedbackShort"),
                "recovery_time_h": _num(item, "recoveryTime"),
                "sleep_score": _num(item, "sleepScore"),
                "hrv_factor_pct": _num(item, "hrvFactorPercent"),
                "acute_load": _num(item, "acuteLoad"),
            }
        )
    return {
        "requested_date": requested_date,
        "available": True,
        "entries": entries,
        "source": SOURCE_GARMIN,
    }


def normalize_hrv_daily(raw: dict[str, Any] | None, cdate: str) -> dict[str, Any] | None:
    """One night's HRV summary; None when nothing was recorded."""
    summary = (raw or {}).get("hrvSummary")
    if not summary:
        return None
    return {
        "date": summary.get("calendarDate") or cdate,
        "last_night_avg_ms": _num(summary, "lastNightAvg"),
        "last_night_5min_high_ms": _num(summary, "lastNight5MinHigh"),
        "weekly_avg_ms": _num(summary, "weeklyAvg"),
        "baseline": summary.get("baseline"),
        "status": summary.get("status"),
        "source": SOURCE_GARMIN,
    }


def normalize_sleep_daily(raw: dict[str, Any], cdate: str) -> dict[str, Any] | None:
    """One night's sleep; None when nothing was recorded."""
    dto = raw.get("dailySleepDTO") or {}
    if not _num(dto, "sleepTimeSeconds"):
        return None
    scores = dto.get("sleepScores") or {}
    overall = scores.get("overall") or {}
    return {
        "date": dto.get("calendarDate") or cdate,
        "sleep_start_local": _epoch_ms_iso(dto.get("sleepStartTimestampLocal")),
        "sleep_end_local": _epoch_ms_iso(dto.get("sleepEndTimestampLocal")),
        "total_sleep_s": _num(dto, "sleepTimeSeconds"),
        "deep_s": _num(dto, "deepSleepSeconds"),
        "light_s": _num(dto, "lightSleepSeconds"),
        "rem_s": _num(dto, "remSleepSeconds"),
        "awake_s": _num(dto, "awakeSleepSeconds"),
        "sleep_score": _num(overall, "value"),
        "sleep_score_qualifier": overall.get("qualifierKey"),
        "avg_overnight_hrv_ms": _num(raw, "avgOvernightHrv"),
        "resting_hr_bpm": _num(raw, "restingHeartRate"),
        "body_battery_change": _num(raw, "bodyBatteryChange"),
        "avg_sleep_stress": _num(dto, "avgSleepStress"),
        "source": SOURCE_GARMIN,
    }


def normalize_rhr_daily(raw: dict[str, Any], cdate: str) -> dict[str, Any] | None:
    """Resting heart rate for one day; None when not recorded."""
    metrics = ((raw.get("allMetrics") or {}).get("metricsMap") or {}).get(
        "WELLNESS_RESTING_HEART_RATE"
    ) or []
    for entry in metrics:
        value = _num(entry, "value")
        if value is not None:
            return {
                "date": entry.get("calendarDate") or cdate,
                "resting_hr_bpm": value,
                "source": SOURCE_GARMIN,
            }
    return None


def normalize_vo2max(raw: list[dict[str, Any]] | dict[str, Any], cdate: str) -> dict[str, Any]:
    """VO2 max from the max-metrics endpoint (cycling-specific when present)."""
    item: dict[str, Any] = raw[0] if isinstance(raw, list) and raw else (
        raw if isinstance(raw, dict) else {}
    )
    cycling = item.get("cycling") or {}
    generic = item.get("generic") or {}
    best = cycling or generic
    return {
        "date": best.get("calendarDate") or cdate,
        "vo2max_cycling": _num(cycling, "vo2MaxPreciseValue") or _num(cycling, "vo2MaxValue"),
        "vo2max_generic": _num(generic, "vo2MaxPreciseValue") or _num(generic, "vo2MaxValue"),
        "fitness_age": _num(generic, "fitnessAge"),
        "source": SOURCE_GARMIN,
    }


def normalize_ftp(raw: dict[str, Any]) -> dict[str, Any]:
    """Current cycling FTP as stored in Garmin Connect."""
    return {
        "ftp_w": _num(raw, "functionalThresholdPower"),
        "set_on": _iso(raw.get("calendarDate")),
        "is_stale": raw.get("isStale"),
        "source_type": raw.get("biometricSourceType"),
        "source": SOURCE_GARMIN,
        "power_note": SINGLE_SIDED_POWER_NOTE,
    }


_COMPARE_KEYS = [
    "duration_s",
    "moving_duration_s",
    "distance_km",
    "elevation_gain_m",
    "avg_speed_kmh",
    "avg_hr_bpm",
    "max_hr_bpm",
    "avg_power_w",
    "normalized_power_w",
    "max_power_20min_w",
    "intensity_factor",
    "training_stress_score",
    "avg_cadence_rpm",
    "training_load",
    "calories_kcal",
]


def compare_summaries(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Side-by-side of two normalized summaries; deltas are calculated locally."""
    deltas: dict[str, float | None] = {}
    for key in _COMPARE_KEYS:
        va, vb = a.get(key), b.get(key)
        deltas[key] = round(vb - va, 3) if va is not None and vb is not None else None
    return {
        "activity_a": a,
        "activity_b": b,
        "deltas_b_minus_a": deltas,
        "deltas_source": "calculated locally from Garmin-recorded values",
    }
