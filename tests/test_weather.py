import json
from pathlib import Path

from garmin_coach import weather
from garmin_coach.normalize import normalize_activity_weather

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


def test_forecast_normalizes_daily_and_hourly() -> None:
    result = weather.get_forecast(days=3, fetch=lambda: load("open_meteo.json"))
    assert result["source"] == "open-meteo"
    assert len(result["daily"]) == 3
    day2 = result["daily"][1]
    assert day2["date"] == "2026-07-26"
    assert day2["temp_max_c"] == 16.7
    assert day2["precip_probability_pct"] == 90
    assert day2["conditions"] == "rain"  # WMO 63
    # hourly kept at 3h stride
    assert [h["time"] for h in result["next_36h"]] == [
        "2026-07-25T00:00",
        "2026-07-25T03:00",
        "2026-07-25T06:00",
    ]


def test_forecast_days_clamped() -> None:
    result = weather.get_forecast(days=99, fetch=lambda: load("open_meteo.json"))
    assert len(result["daily"]) == 3  # fixture only has 3, clamp asks for max 7


def test_activity_weather_converts_units_and_nulls() -> None:
    w = normalize_activity_weather(load("activity_weather.json"), 100000003)
    assert w["temp_c"] == 18.3  # 65 F
    assert w["dew_point_c"] == 13.3
    assert w["humidity_pct"] == 74.0
    assert w["wind_kmh"] is None  # station reported null, stays null
    assert w["conditions"] is None  # "Unknown" mapped to None
    assert w["wind_direction"] == "n"
    assert w["source"] == "garmin"
