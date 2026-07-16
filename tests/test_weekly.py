from datetime import date

from garmin_coach.normalize import build_weekly_summaries, normalize_ride_summaries


def ride(activity_id: int, start_local: str, load: float | None = 100.0, **extra: object) -> dict:
    raw: dict = {
        "activityId": activity_id,
        "activityName": f"Ride {activity_id}",
        "startTimeLocal": start_local,
        "activityType": {"typeKey": "road_biking"},
        "distance": 30000.0,
        "duration": 3600.0,
        "movingDuration": 3500.0,
        "elevationGain": 300.0,
    }
    if load is not None:
        raw["activityTrainingLoad"] = load
    raw.update(extra)
    return raw


def test_weekly_grouping_and_totals() -> None:
    # Mon 2026-07-06 .. Thu 2026-07-16 spans two ISO weeks
    rides = normalize_ride_summaries(
        [
            ride(3, "2026-07-16 08:00:00", load=150.0),
            ride(2, "2026-07-14 09:00:00", load=60.0),
            ride(1, "2026-07-08 09:00:00", load=90.0),
        ]
    )
    weeks = build_weekly_summaries(rides, date(2026, 7, 6), date(2026, 7, 16))

    assert [w["week_start"] for w in weeks] == ["2026-07-13", "2026-07-06"]
    current = weeks[0]
    assert current["ride_count"] == 2
    assert current["total_distance_km"] == 60.0
    assert current["total_duration_h"] == 2.0
    assert current["total_training_load"] == 210.0
    assert current["hardest_ride"]["activity_id"] == 3
    assert current["hardest_ride"]["training_load"] == 150.0
    prev = weeks[1]
    assert prev["ride_count"] == 1
    assert prev["week_end"] == "2026-07-12"


def test_empty_weeks_are_reported_not_dropped() -> None:
    rides = normalize_ride_summaries([ride(1, "2026-07-16 08:00:00")])
    weeks = build_weekly_summaries(rides, date(2026, 6, 29), date(2026, 7, 16))

    assert len(weeks) == 3
    empty = [w for w in weeks if w["ride_count"] == 0]
    assert len(empty) == 2
    assert empty[0]["total_distance_km"] is None
    assert empty[0]["hardest_ride"] is None


def test_rides_without_load_still_counted() -> None:
    rides = normalize_ride_summaries([ride(1, "2026-07-16 08:00:00", load=None)])
    weeks = build_weekly_summaries(rides, date(2026, 7, 13), date(2026, 7, 16))
    assert weeks[0]["ride_count"] == 1
    assert weeks[0]["total_training_load"] is None
    assert weeks[0]["hardest_ride"] is None
