"""Local read-only Garmin MCP server: `garmin-mcp`.

Exposes Garmin Connect data to Claude over stdio. Milestone 2 ships exactly
one tool (get_recent_activities); more arrive in Milestone 3.

stdio discipline: stdout carries only the MCP protocol — all logging goes to
stderr, and credentials/tokens are never logged anywhere.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import GarminClient, GarminClientError, ReauthRequiredError
from .normalize import (
    build_weekly_summaries,
    compare_summaries,
    normalize_activity_summary,
    normalize_courses,
    normalize_fitness_age,
    normalize_ftp,
    normalize_hrv_daily,
    normalize_laps,
    normalize_rhr_daily,
    normalize_ride_summaries,
    normalize_sleep_daily,
    normalize_time_series,
    normalize_training_readiness,
    normalize_training_status,
    normalize_vo2max,
    normalize_zones,
)

MAX_LIMIT = 50
MAX_HISTORY_DAYS = 14
MAX_SUMMARY_WEEKS = 12
MAX_WELLNESS_DAYS = 7

mcp = FastMCP(
    "garmin-coach",
    instructions=(
        "Read-only access to the user's Garmin Connect cycling data. "
        "All values are normalized with units in field names and ISO-8601 timestamps; "
        "`source` marks provenance. Rides with power include a `power_note`: the user's "
        "Rally RS100 is single-sided (left-leg doubled), so never infer left/right balance."
    ),
    log_level="WARNING",
)

_cached_client: GarminClient | None = None


def _client() -> GarminClient:
    """Lazily create and cache the Garmin session (login only on first tool call)."""
    global _cached_client
    if _cached_client is None:
        _cached_client = GarminClient.from_saved_tokens()
    return _cached_client


def _drop_client() -> None:
    global _cached_client
    _cached_client = None


def _call[T](fn: Callable[[GarminClient], T]) -> T:
    """Run one client operation, converting client errors into readable tool errors."""
    try:
        return fn(_client())
    except ReauthRequiredError as e:
        _drop_client()  # next call re-reads tokens in case the user re-ran garmin-setup
        raise RuntimeError(str(e)) from e
    except GarminClientError as e:
        raise RuntimeError(str(e)) from e


def _valid_date(value: str | None) -> str:
    """Validate an optional YYYY-MM-DD date; default to today."""
    if value is None or value == "":
        return date.today().isoformat()
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as e:
        raise RuntimeError(f"Invalid date {value!r}: expected YYYY-MM-DD") from e


def _history_dates(days: int, end_date: str | None) -> list[str]:
    """Most recent `days` calendar dates ending at end_date (default today), oldest first."""
    days = max(1, min(int(days), MAX_HISTORY_DAYS))
    end = date.fromisoformat(_valid_date(end_date))
    return [(end - timedelta(days=offset)).isoformat() for offset in range(days - 1, -1, -1)]


@mcp.tool()
def get_recent_activities(limit: int = 5) -> list[dict[str, Any]]:
    """Get the user's most recent cycling activities from Garmin Connect, newest first.

    Args:
        limit: Number of activities to return (1-50, default 5).

    Returns normalized ride summaries: distance_km, duration_s, elevation_gain_m,
    avg/max power_w, normalized_power_w (Garmin-reported, not locally calculated),
    avg/max hr_bpm, avg_cadence_rpm, calories_kcal, training_load, training effects,
    ISO-8601 start times, and source provenance. Missing sensor data is null, never
    guessed. Rides with power carry a single-sided power meter caveat in power_note.
    """
    limit = max(1, min(int(limit), MAX_LIMIT))
    raw = _call(lambda c: c.recent_cycling_activities(limit=limit))
    return [ride.to_dict() for ride in normalize_ride_summaries(raw)]


@mcp.tool()
def get_activity_summary(activity_id: int) -> dict[str, Any]:
    """Get the full summary of one activity: distance, duration, elevation, speed,
    heart rate, power (avg/max/normalized/20-min max), Garmin-reported intensity
    factor and training stress score with the FTP used at ride time, cadence,
    temperature, respiration, stamina, and training effects. Missing sensors are null.
    """
    return normalize_activity_summary(_call(lambda c: c.activity_summary(str(activity_id))))


@mcp.tool()
def get_activity_splits(activity_id: int) -> dict[str, Any]:
    """Get per-lap splits for one activity (as recorded by the Edge unit): duration,
    distance, elevation, speed, heart rate, power (avg/max/normalized), cadence.
    Useful for pacing analysis across a ride.
    """
    return normalize_laps(_call(lambda c: c.activity_splits(str(activity_id))))


@mcp.tool()
def get_activity_power_data(activity_id: int) -> dict[str, Any]:
    """Get time-in-power-zone data for one activity: seconds and share per zone with
    the zone's lower watt boundary (boundaries from the user's Garmin power zones).
    Single-sided power meter caveat applies: never infer left/right balance.
    """
    raw = _call(lambda c: c.activity_power_zones(str(activity_id)))
    result = normalize_zones(raw, unit="w")
    result["activity_id"] = activity_id
    return result


@mcp.tool()
def get_activity_heart_rate_data(activity_id: int) -> dict[str, Any]:
    """Get time-in-heart-rate-zone data for one activity: seconds and share per zone
    with the zone's lower bpm boundary (boundaries from the user's Garmin HR zones).
    """
    raw = _call(lambda c: c.activity_hr_zones(str(activity_id)))
    result = normalize_zones(raw, unit="bpm")
    result["activity_id"] = activity_id
    return result


@mcp.tool()
def get_activity_details(activity_id: int, max_points: int = 150) -> dict[str, Any]:
    """Get downsampled time-series streams for one activity: elapsed offset, distance,
    power, heart rate, cadence, speed, elevation at ~max_points evenly spaced samples
    (10-500, default 150). Use for pacing, drift, and interval-shape analysis.
    """
    max_points = max(10, min(int(max_points), 500))
    raw = _call(lambda c: c.activity_details(str(activity_id), max_points=max_points))
    return normalize_time_series(raw)


@mcp.tool()
def compare_activities(activity_id_a: int, activity_id_b: int) -> dict[str, Any]:
    """Compare two activities side by side: both normalized summaries plus per-metric
    deltas (b minus a, calculated locally from Garmin-recorded values).
    """
    a = normalize_activity_summary(_call(lambda c: c.activity_summary(str(activity_id_a))))
    b = normalize_activity_summary(_call(lambda c: c.activity_summary(str(activity_id_b))))
    return compare_summaries(a, b)


@mcp.tool()
def get_training_status(for_date: str | None = None) -> dict[str, Any]:
    """Get Garmin training status for a date (YYYY-MM-DD, default today): status phrase,
    acute/chronic load with ACWR, monthly aerobic-low/high and anaerobic load vs. target
    ranges, load-balance feedback, and current cycling VO2 max.
    """
    cdate = _valid_date(for_date)
    return normalize_training_status(_call(lambda c: c.training_status(cdate)), cdate)


@mcp.tool()
def get_training_readiness(for_date: str | None = None) -> dict[str, Any]:
    """Get Garmin training readiness for a date (YYYY-MM-DD, default today).
    Note: readiness is computed by Garmin watches; an Edge bike computer alone does
    not produce it — the result says explicitly when it is unavailable.
    """
    cdate = _valid_date(for_date)
    return normalize_training_readiness(_call(lambda c: c.training_readiness(cdate)), cdate)


@mcp.tool()
def get_recovery_time(for_date: str | None = None) -> dict[str, Any]:
    """Get post-exercise recovery time if Garmin exposes it for this account.
    Recovery hours shown on the Edge 540 screen are not available through
    Garmin Connect for device-only accounts; when absent this says so explicitly
    rather than estimating.
    """
    cdate = _valid_date(for_date)
    readiness = normalize_training_readiness(_call(lambda c: c.training_readiness(cdate)), cdate)
    for entry in readiness["entries"]:
        if entry.get("recovery_time_h") is not None:
            return {
                "requested_date": cdate,
                "available": True,
                "recovery_time_h": entry["recovery_time_h"],
                "as_of": entry.get("timestamp_local"),
                "source": "garmin",
            }
    return {
        "requested_date": cdate,
        "available": False,
        "recovery_time_h": None,
        "note": (
            "Recovery time is not exposed via Garmin Connect for this account "
            "(it requires training readiness data from a Garmin watch). "
            "The value shown on the Edge 540 itself is not retrievable."
        ),
        "source": "garmin",
    }


@mcp.tool()
def get_hrv_history(days: int = 7, end_date: str | None = None) -> dict[str, Any]:
    """Get nightly HRV summaries for the last `days` days (1-14, default 7): last-night
    average and 5-min high, rolling weekly average, baseline, and Garmin's HRV status.
    Days without a recording are listed under missing_dates.
    """
    entries: list[dict[str, Any]] = []
    missing: list[str] = []
    for cdate in _history_dates(days, end_date):

        def fetch(d: str = cdate) -> dict[str, Any] | None:
            return _call(lambda c: c.hrv_daily(d))

        raw = fetch()
        normalized = normalize_hrv_daily(raw, cdate)
        if normalized:
            entries.append(normalized)
        else:
            missing.append(cdate)
    return {"days": entries, "missing_dates": missing, "source": "garmin"}


@mcp.tool()
def get_sleep_history(days: int = 7, end_date: str | None = None) -> dict[str, Any]:
    """Get nightly sleep for the last `days` days (1-14, default 7): start/end, stage
    durations (deep/light/REM/awake), sleep score, overnight HRV, resting HR, and
    body-battery change. Nights without a recording are listed under missing_dates.
    """
    entries: list[dict[str, Any]] = []
    missing: list[str] = []
    for cdate in _history_dates(days, end_date):

        def fetch(d: str = cdate) -> dict[str, Any]:
            return _call(lambda c: c.sleep_daily(d))

        raw = fetch()
        normalized = normalize_sleep_daily(raw, cdate)
        if normalized:
            entries.append(normalized)
        else:
            missing.append(cdate)
    return {"nights": entries, "missing_dates": missing, "source": "garmin"}


@mcp.tool()
def get_resting_heart_rate_history(days: int = 7, end_date: str | None = None) -> dict[str, Any]:
    """Get daily resting heart rate for the last `days` days (1-14, default 7).
    Days without a recording are listed under missing_dates.
    """
    entries: list[dict[str, Any]] = []
    missing: list[str] = []
    for cdate in _history_dates(days, end_date):

        def fetch(d: str = cdate) -> dict[str, Any]:
            return _call(lambda c: c.rhr_daily(d))

        raw = fetch()
        normalized = normalize_rhr_daily(raw, cdate)
        if normalized:
            entries.append(normalized)
        else:
            missing.append(cdate)
    return {"days": entries, "missing_dates": missing, "source": "garmin"}


@mcp.tool()
def get_vo2_max(for_date: str | None = None) -> dict[str, Any]:
    """Get the user's VO2 max as of a date (YYYY-MM-DD, default today), cycling-specific
    and generic values plus a VO2-max-derived fitness age. Note: the Connect app
    displays a different, multi-component fitness age — use get_fitness_age for that.
    """
    cdate = _valid_date(for_date)
    return normalize_vo2max(_call(lambda c: c.max_metrics(cdate)), cdate)


@mcp.tool()
def get_fitness_age(for_date: str | None = None) -> dict[str, Any]:
    """Get Garmin fitness age for a date (YYYY-MM-DD, default today) — the value the
    Connect app displays, computed from chronological age, weekly vigorous activity
    (days and minutes), resting heart rate, and BMI, each returned with its target
    where Garmin provides one. Prefer this over get_vo2_max's fitness_age when the
    user asks about fitness age.
    """
    cdate = _valid_date(for_date)
    return normalize_fitness_age(_call(lambda c: c.fitness_age(cdate)), cdate)


@mcp.tool()
def get_current_ftp() -> dict[str, Any]:
    """Get the user's current cycling FTP as stored in Garmin Connect, with the date it
    was set and whether Garmin considers it stale. Use this before any zone- or
    intensity-based interpretation.
    """
    return normalize_ftp(_call(lambda c: c.cycling_ftp()))


@mcp.tool()
def get_weekly_training_summary(weeks: int = 4, end_date: str | None = None) -> dict[str, Any]:
    """Get per-week training totals for the last `weeks` ISO weeks (Mon-Sun, 1-12,
    default 4, newest first): ride count, duration, distance, elevation, summed
    Garmin training load, and the hardest ride of each week. Use this as the
    baseline when judging whether a ride was big or small for the user.
    """
    weeks = max(1, min(int(weeks), MAX_SUMMARY_WEEKS))
    end = date.fromisoformat(_valid_date(end_date))
    start = end - timedelta(days=end.weekday() + 7 * (weeks - 1))
    raw = _call(lambda c: c.cycling_activities_by_date(start.isoformat(), end.isoformat()))
    rides = normalize_ride_summaries(raw)
    return {
        "range_start": start.isoformat(),
        "range_end": end.isoformat(),
        "weeks": build_weekly_summaries(rides, start, end),
        "note": (
            "totals are summed locally from Garmin-recorded per-ride values; "
            "weekly TSS is unavailable because Garmin's activity list omits per-ride TSS"
        ),
    }


@mcp.tool()
def get_training_plan_context(wellness_days: int = 3) -> dict[str, Any]:
    """Get everything needed to build a 7-day training plan in one call: current FTP,
    VO2 max, training status (acute/chronic load, ACWR, load balance), the last 14 days
    of rides with totals, and recent sleep/HRV/resting-HR (`wellness_days` days, 1-7).
    Ask the user for subjective fatigue, available days, and indoor/outdoor preference
    separately — those are not in Garmin.
    """
    wellness_days = max(1, min(int(wellness_days), MAX_WELLNESS_DAYS))
    today = date.today()
    today_iso = today.isoformat()
    start = (today - timedelta(days=13)).isoformat()

    ftp = normalize_ftp(_call(lambda c: c.cycling_ftp()))
    vo2 = normalize_vo2max(_call(lambda c: c.max_metrics(today_iso)), today_iso)
    status = normalize_training_status(_call(lambda c: c.training_status(today_iso)), today_iso)
    raw_rides = _call(lambda c: c.cycling_activities_by_date(start, today_iso))
    rides = [r.to_dict() for r in normalize_ride_summaries(raw_rides)]

    sleep: list[dict[str, Any]] = []
    hrv: list[dict[str, Any]] = []
    rhr: list[dict[str, Any]] = []
    for cdate in _history_dates(wellness_days, today_iso):

        def fetch_day(d: str = cdate) -> tuple[Any, Any, Any]:
            return (
                _call(lambda c: c.sleep_daily(d)),
                _call(lambda c: c.hrv_daily(d)),
                _call(lambda c: c.rhr_daily(d)),
            )

        raw_sleep, raw_hrv, raw_rhr = fetch_day()
        if s := normalize_sleep_daily(raw_sleep, cdate):
            sleep.append(s)
        if h := normalize_hrv_daily(raw_hrv, cdate):
            hrv.append(h)
        if r := normalize_rhr_daily(raw_rhr, cdate):
            rhr.append(r)

    load_values = [r["training_load"] for r in rides if r["training_load"] is not None]
    return {
        "as_of": today_iso,
        "ftp": ftp,
        "vo2max": vo2,
        "training_status": status,
        "last_14_days": {
            "ride_count": len(rides),
            "total_training_load": round(sum(load_values), 1) if load_values else None,
            "rides": rides,
        },
        "recent_sleep": sleep,
        "recent_hrv": hrv,
        "recent_resting_hr": rhr,
        "notes": [
            "training readiness and recovery time are unavailable (no Garmin watch)",
            "power values come from a single-sided meter (left-leg doubled)",
            "subjective fatigue, soreness, available days and indoor/outdoor "
            "preference must come from the user",
        ],
    }


@mcp.prompt(title="Build a 7-day cycling training plan")
def plan_week(goal: str = "", days_available: str = "", constraints: str = "") -> str:
    """Guide Claude through building an adaptive rolling 7-day cycling plan."""
    user_context = ""
    if goal:
        user_context += f"\nStated goal: {goal}"
    if days_available:
        user_context += f"\nDays available to ride: {days_available}"
    if constraints:
        user_context += f"\nConstraints: {constraints}"
    return f"""Build me a rolling 7-day cycling training plan.{user_context}

Follow this process:
1. Call get_training_plan_context and get_weekly_training_summary (4 weeks) first.
2. If my goal, available days, indoor/outdoor preference, or subjective fatigue and
   soreness are unknown, ask me before writing the plan.
3. Judge my recovery from the data (sleep, HRV vs. weekly average, resting-HR trend,
   ACWR, recent training load) and say explicitly which signals informed the plan.

The plan must contain, for each day (including rest days):
- Session purpose (e.g. threshold development, endurance, recovery)
- Duration
- Intensity target as watts (derived from my current FTP from get_current_ftp or the
  context call), heart rate, or perceived effort - state which
- Interval and recovery instructions where applicable
- An easier alternative to use if my recovery indicators are poor that morning
- One or two sentences on why this session, given my recent load and goals

Rules:
- Distinguish recorded facts, calculated values, and coaching interpretation.
- Do not invent zone boundaries; use FTP-anchored ranges and label them as such.
- My power meter is single-sided - never reference left/right balance.
- If data is missing or conflicting, say so instead of guessing.
- Do not diagnose medical conditions.
- Do not schedule or upload workouts to my device; present the plan in chat only."""


@mcp.tool()
def get_courses() -> list[dict[str, Any]]:
    """Get the user's saved Garmin courses (routes) with distance and climbing, longest
    first. Use when the user asks about fueling, pacing, or planning a named route —
    estimate ride duration from distance, elevation gain, and the user's demonstrated
    speeds, and state the estimate as an assumption.
    """
    return normalize_courses(_call(lambda c: c.courses()))


def main() -> None:
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    logging.getLogger("garminconnect").setLevel(logging.ERROR)
    logging.getLogger("garth").setLevel(logging.ERROR)
    mcp.run()  # stdio transport


if __name__ == "__main__":
    main()
