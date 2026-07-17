"""Read-only dashboard API.

Every endpoint is a thin wrapper over the MCP server's tool functions so the
web app and Claude see identical normalized data. Tool errors carry the
original typed cause, which maps to meaningful HTTP statuses here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from .. import server
from ..client import RateLimitedError, ReauthRequiredError

PLAN_DIR = Path(__file__).resolve().parents[3] / "training"

router = APIRouter(prefix="/api")


def _call_tool(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Invoke a server tool function, mapping failures to HTTP errors."""
    try:
        return fn(*args, **kwargs)
    except RuntimeError as e:
        cause = e.__cause__
        if isinstance(cause, ReauthRequiredError):
            raise HTTPException(status_code=401, detail=str(e)) from e
        if isinstance(cause, RateLimitedError):
            raise HTTPException(status_code=429, detail=str(e)) from e
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.get("/rides")
def rides(limit: int = 10) -> list[dict[str, Any]]:
    return _call_tool(server.get_recent_activities, limit=limit)  # type: ignore[no-any-return]


@router.get("/rides/{activity_id}")
def ride_detail(activity_id: int, max_points: int = 200) -> dict[str, Any]:
    return {
        "summary": _call_tool(server.get_activity_summary, activity_id),
        "power_zones": _call_tool(server.get_activity_power_data, activity_id),
        "hr_zones": _call_tool(server.get_activity_heart_rate_data, activity_id),
        "splits": _call_tool(server.get_activity_splits, activity_id),
        "series": _call_tool(server.get_activity_details, activity_id, max_points=max_points),
    }


@router.get("/weekly")
def weekly(weeks: int = 8) -> dict[str, Any]:
    return _call_tool(server.get_weekly_training_summary, weeks=weeks)  # type: ignore[no-any-return]


@router.get("/wellness")
def wellness(days: int = 7) -> dict[str, Any]:
    return {
        "sleep": _call_tool(server.get_sleep_history, days=days),
        "hrv": _call_tool(server.get_hrv_history, days=days),
        "resting_hr": _call_tool(server.get_resting_heart_rate_history, days=days),
    }


@router.get("/status")
def status() -> dict[str, Any]:
    return {
        "training_status": _call_tool(server.get_training_status),
        "ftp": _call_tool(server.get_current_ftp),
        "vo2max": _call_tool(server.get_vo2_max),
        "fitness_age": _call_tool(server.get_fitness_age),
    }


@router.get("/plan")
def plan() -> dict[str, Any]:
    plans = sorted(PLAN_DIR.glob("*.md")) if PLAN_DIR.exists() else []
    if not plans:
        raise HTTPException(status_code=404, detail="No training plan found in training/")
    newest = plans[-1]
    return {"name": newest.stem, "markdown": newest.read_text()}
