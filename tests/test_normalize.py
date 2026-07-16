import json
from pathlib import Path

from garmin_coach.models import SINGLE_SIDED_POWER_NOTE, SOURCE_GARMIN
from garmin_coach.normalize import normalize_ride_summaries, normalize_ride_summary

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture() -> list[dict]:
    return json.loads((FIXTURES / "activity_list.json").read_text())


def test_full_sensor_ride_normalizes_all_fields() -> None:
    ride = normalize_ride_summary(load_fixture()[0])

    assert ride.activity_id == 100000001
    assert ride.name == "Morning Climb Repeats"
    assert ride.activity_type == "road_biking"
    assert ride.start_time_local == "2026-07-12T06:42:11"
    assert ride.start_time_utc == "2026-07-11T20:42:11"
    assert ride.duration_s == 6488.0
    assert ride.distance_km == 46.28
    assert ride.elevation_gain_m == 612.0
    assert ride.avg_speed_kmh == 25.7  # 7.132 m/s * 3.6, rounded
    assert ride.avg_hr_bpm == 148.0
    assert ride.max_hr_bpm == 181.0
    assert ride.avg_power_w == 186.0
    assert ride.normalized_power_w == 204.0  # Garmin-reported, not calculated locally
    assert ride.avg_cadence_rpm == 84.0
    assert ride.calories_kcal == 1245
    assert ride.training_load == 173.4
    assert ride.source == SOURCE_GARMIN
    assert ride.power_note == SINGLE_SIDED_POWER_NOTE


def test_sensorless_ride_yields_none_not_guesses() -> None:
    ride = normalize_ride_summary(load_fixture()[1])

    assert ride.avg_power_w is None
    assert ride.max_power_w is None
    assert ride.normalized_power_w is None
    assert ride.avg_hr_bpm is None
    assert ride.avg_cadence_rpm is None
    assert ride.power_note is None  # no power -> no single-sided caveat needed
    assert ride.distance_km == 20.15
    assert ride.training_load is None


def test_normalize_list_preserves_order() -> None:
    rides = normalize_ride_summaries(load_fixture())
    assert [r.activity_id for r in rides] == [100000001, 100000002]


def test_missing_optional_fields_do_not_crash() -> None:
    ride = normalize_ride_summary({"activityId": 1})
    assert ride.activity_id == 1
    assert ride.name == "Untitled activity"
    assert ride.activity_type == "unknown"
    assert ride.start_time_local is None
    assert ride.distance_km is None


def test_boolean_values_are_not_mistaken_for_numbers() -> None:
    ride = normalize_ride_summary({"activityId": 1, "distance": True})
    assert ride.distance_km is None
