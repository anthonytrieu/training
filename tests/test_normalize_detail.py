import json
from pathlib import Path
from typing import Any

from garmin_coach.normalize import (
    compare_summaries,
    normalize_activity_summary,
    normalize_ftp,
    normalize_hrv_daily,
    normalize_laps,
    normalize_rhr_daily,
    normalize_sleep_daily,
    normalize_time_series,
    normalize_training_readiness,
    normalize_training_status,
    normalize_vo2max,
    normalize_zones,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


def test_activity_summary_includes_garmin_reported_intensity_metrics() -> None:
    s = normalize_activity_summary(load("activity_summary.json"))
    assert s["activity_id"] == 100000001
    assert s["location"] == "Vancouver"
    assert s["distance_km"] == 34.27
    assert s["ftp_at_ride_w"] == 290.0
    assert s["intensity_factor"] == 0.485
    assert s["training_stress_score"] == 45.3
    assert s["max_power_20min_w"] == 137.6
    assert s["normalized_power_w"] == 141.0
    assert s["avg_moving_speed_kmh"] == 22.9
    assert s["min_hr_bpm"] == 70.0
    assert s["end_stamina_pct"] == 81.0
    assert "Garmin-reported" in s["garmin_reported_note"]
    assert "single-sided" in s["power_note"]
    assert s["source"] == "garmin"


def test_laps_normalize_in_order() -> None:
    result = normalize_laps(load("activity_splits.json"))
    assert result["lap_count"] == 5
    lap1 = result["laps"][0]
    assert lap1["lap_index"] == 1
    assert lap1["distance_km"] == 8.05
    assert lap1["avg_power_w"] == 62.0
    assert lap1["normalized_power_w"] == 107.0
    assert lap1["avg_hr_bpm"] == 121.0


def test_hr_zones_shares_sum_to_100() -> None:
    result = normalize_zones(load("activity_hr_zones.json"), unit="bpm")
    assert len(result["zones"]) == 5
    assert result["zones"][0]["low_boundary_bpm"] == 99.0
    total_pct = sum(z["share_pct"] for z in result["zones"])
    assert 99.5 <= total_pct <= 100.5
    assert "calculated locally" in result["note"]


def test_power_zones_have_watt_boundaries() -> None:
    result = normalize_zones(load("activity_power_zones.json"), unit="w")
    assert len(result["zones"]) == 7
    assert result["zones"][1]["low_boundary_w"] == 159.0
    assert result["zones"][0]["share_pct"] > 50  # mostly zone 1 ride


def test_time_series_maps_descriptor_indices() -> None:
    result = normalize_time_series(load("activity_details.json"))
    assert result["point_count"] == 5
    first = result["points"][0]
    assert first["hr_bpm"] == 103.0
    assert first["power_w"] == 0.0
    assert first["cadence_rpm"] == 123.0
    assert first["speed_kmh"] == 15.6  # 4.329 m/s * 3.6
    assert first["elevation_m"] == 49.6
    assert first["offset_s"] == 0.0


def test_training_status_picks_primary_device() -> None:
    s = normalize_training_status(load("training_status.json"), "2026-07-16")
    assert s["training_status_phrase"] == "MAINTAINING_4"
    assert s["acute_load"] == 647.0
    assert s["chronic_load"] == 628.0
    assert s["acwr_status"] == "OPTIMAL"
    assert s["monthly_load_aerobic_low"] == 1102.2
    assert s["load_balance_phrase"] == "AEROBIC_LOW_FOCUS"
    assert s["vo2max_cycling"] == 63.7
    assert s["training_paused"] is False


def test_training_readiness_empty_is_flagged_unavailable() -> None:
    r = normalize_training_readiness([], "2026-07-16")
    assert r["available"] is False
    assert "watch" in r["note"]


def test_hrv_daily() -> None:
    h = normalize_hrv_daily(load("hrv_data.json"), "2026-07-16")
    assert h is not None
    assert h["last_night_avg_ms"] == 58.0
    assert h["weekly_avg_ms"] == 60.0
    assert h["status"] == "NONE"


def test_hrv_daily_none_when_no_summary() -> None:
    assert normalize_hrv_daily(None, "2026-07-16") is None
    assert normalize_hrv_daily({"hrvSummary": None}, "2026-07-16") is None


def test_sleep_daily() -> None:
    s = normalize_sleep_daily(load("sleep_data.json"), "2026-07-16")
    assert s is not None
    assert s["total_sleep_s"] == 21300.0
    assert s["deep_s"] == 7680.0
    assert s["sleep_score"] == 72.0
    assert s["sleep_score_qualifier"] == "FAIR"
    assert s["resting_hr_bpm"] == 52.0
    assert s["avg_overnight_hrv_ms"] == 58.0
    assert s["sleep_start_local"] is not None and "T" in s["sleep_start_local"]


def test_sleep_daily_none_when_unrecorded() -> None:
    assert normalize_sleep_daily({"dailySleepDTO": {"sleepTimeSeconds": None}}, "x") is None
    assert normalize_sleep_daily({}, "x") is None


def test_rhr_daily() -> None:
    r = normalize_rhr_daily(load("rhr_day.json"), "2026-07-16")
    assert r is not None
    assert r["resting_hr_bpm"] == 52.0
    assert r["date"] == "2026-07-16"


def test_rhr_daily_none_when_missing() -> None:
    assert normalize_rhr_daily({"allMetrics": {"metricsMap": {}}}, "x") is None


def test_vo2max() -> None:
    v = normalize_vo2max(load("max_metrics.json"), "2026-07-16")
    assert v["vo2max_cycling"] == 63.7
    assert v["fitness_age"] == 20.0


def test_ftp() -> None:
    f = normalize_ftp(load("cycling_ftp.json"))
    assert f["ftp_w"] == 290.0
    assert f["is_stale"] is False
    assert "single-sided" in f["power_note"]


def test_compare_summaries_deltas() -> None:
    s = normalize_activity_summary(load("activity_summary.json"))
    shorter = dict(s, distance_km=20.0, avg_power_w=100.0, avg_hr_bpm=None)
    result = compare_summaries(s, shorter)
    assert result["deltas_b_minus_a"]["distance_km"] == -14.27
    assert result["deltas_b_minus_a"]["avg_power_w"] == 24.0
    assert result["deltas_b_minus_a"]["avg_hr_bpm"] is None  # missing data stays missing
    assert "calculated locally" in result["deltas_source"]
