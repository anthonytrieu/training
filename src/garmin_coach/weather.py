"""Weather forecast via Open-Meteo (free, no API key, metric).

Used for planning: session scheduling, fueling, and coach advice. Recorded
per-ride weather comes from Garmin instead (see normalize_activity_weather).
"""

from __future__ import annotations

import time
from typing import Any

import requests

# Vancouver — right for all current riding/courses.
LATITUDE = 49.26
LONGITUDE = -123.11
TIMEZONE = "America/Vancouver"

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
CACHE_TTL_S = 30 * 60

# WMO weather interpretation codes → short descriptions.
WMO_CODES = {
    0: "clear",
    1: "mostly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "fog",
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    56: "freezing drizzle",
    57: "freezing drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    66: "freezing rain",
    67: "freezing rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    77: "snow grains",
    80: "light showers",
    81: "showers",
    82: "heavy showers",
    85: "snow showers",
    86: "snow showers",
    95: "thunderstorm",
    96: "thunderstorm w/ hail",
    99: "thunderstorm w/ hail",
}

_cache: dict[str, Any] = {"at": 0.0, "data": None}


class WeatherUnavailableError(Exception):
    """Open-Meteo could not be reached or answered unexpectedly."""


def _describe(code: Any) -> str | None:
    return WMO_CODES.get(code) if isinstance(code, int) else None


def _fetch_raw() -> dict[str, Any]:
    params: dict[str, str | float | int] = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "timezone": TIMEZONE,
        "forecast_days": 7,
        "daily": (
            "temperature_2m_max,temperature_2m_min,"
            "precipitation_probability_max,wind_speed_10m_max,weather_code"
        ),
        "hourly": "temperature_2m,precipitation_probability,wind_speed_10m,weather_code",
    }
    resp = requests.get(FORECAST_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()  # type: ignore[no-any-return]


def get_forecast(days: int = 5, fetch: Any = None) -> dict[str, Any]:
    """Normalized forecast: `days` daily entries + next 36 h in 3 h steps.

    `fetch` is injectable for tests. Results are cached for ~30 minutes.
    """
    days = max(1, min(int(days), 7))
    now = time.time()
    if fetch is None and _cache["data"] is not None and now - _cache["at"] < CACHE_TTL_S:
        raw = _cache["data"]
    else:
        try:
            raw = (fetch or _fetch_raw)()
        except Exception as e:
            raise WeatherUnavailableError(f"Weather forecast unavailable: {e}") from e
        if fetch is None:
            _cache.update(at=now, data=raw)

    daily_raw = raw.get("daily") or {}
    daily = [
        {
            "date": d,
            "temp_max_c": daily_raw["temperature_2m_max"][i],
            "temp_min_c": daily_raw["temperature_2m_min"][i],
            "precip_probability_pct": daily_raw["precipitation_probability_max"][i],
            "wind_max_kmh": daily_raw["wind_speed_10m_max"][i],
            "conditions": _describe(daily_raw["weather_code"][i]),
        }
        for i, d in enumerate(daily_raw.get("time", [])[:days])
    ]

    hourly_raw = raw.get("hourly") or {}
    hourly = [
        {
            "time": t,
            "temp_c": hourly_raw["temperature_2m"][i],
            "precip_probability_pct": hourly_raw["precipitation_probability"][i],
            "wind_kmh": hourly_raw["wind_speed_10m"][i],
            "conditions": _describe(hourly_raw["weather_code"][i]),
        }
        for i, t in enumerate(hourly_raw.get("time", [])[:36])
        if i % 3 == 0
    ]

    return {
        "location": "Vancouver, BC",
        "timezone": TIMEZONE,
        "daily": daily,
        "next_36h": hourly,
        "source": "open-meteo",
    }
