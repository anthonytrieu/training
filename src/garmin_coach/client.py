"""The only module that talks to the garminconnect library.

python-garminconnect wraps Garmin's unofficial web API; if Garmin changes
endpoints, breakage should be contained here. All library exceptions are
mapped to our own error types with user-actionable messages, and nothing
here ever logs credentials or token contents.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from .auth import REAUTH_MESSAGE, token_store_path


class GarminClientError(Exception):
    """Base error for all Garmin client failures."""


class ReauthRequiredError(GarminClientError):
    """Saved session is missing or invalid; user must run `garmin-setup`."""


class RateLimitedError(GarminClientError):
    """Garmin returned 429; caller should wait before retrying."""


class GarminUnavailableError(GarminClientError):
    """Network problem or Garmin-side error."""


@contextmanager
def _mapped_errors() -> Iterator[None]:
    try:
        yield
    except GarminConnectAuthenticationError as e:
        raise ReauthRequiredError(REAUTH_MESSAGE) from e
    except GarminConnectTooManyRequestsError as e:
        raise RateLimitedError(
            "Garmin rate limit hit (HTTP 429). Wait a few minutes before retrying."
        ) from e
    except GarminConnectConnectionError as e:
        raise GarminUnavailableError(
            f"Could not reach Garmin Connect: {e}. "
            "Garmin's unofficial API may be down or may have changed."
        ) from e


class GarminClient:
    """Read-only, session-restoring wrapper over the Garmin API."""

    def __init__(self, api: Garmin) -> None:
        self._api = api

    @classmethod
    def from_saved_tokens(cls, token_dir: Path | None = None) -> GarminClient:
        """Restore a session from tokens saved by `garmin-setup`.

        Raises ReauthRequiredError when tokens are absent or no longer valid.
        """
        path = token_dir or token_store_path()
        if not path.exists():
            raise ReauthRequiredError(REAUTH_MESSAGE)
        api = Garmin()
        with _mapped_errors():
            api.login(str(path))
        return cls(api)

    def recent_cycling_activities(self, limit: int = 5) -> list[dict[str, Any]]:
        """Most recent cycling activities (raw Garmin list items, newest first)."""
        with _mapped_errors():
            activities = self._api.get_activities(start=0, limit=limit, activitytype="cycling")
        if not isinstance(activities, list):
            raise GarminUnavailableError(
                f"Unexpected response shape from Garmin activity list: {type(activities).__name__}"
            )
        return activities

    def cycling_activities_by_date(self, start: str, end: str) -> list[dict[str, Any]]:
        """All cycling activities between two YYYY-MM-DD dates (inclusive), newest first."""
        with _mapped_errors():
            return cast(
                list[dict[str, Any]],
                self._api.get_activities_by_date(start, end, activitytype="cycling"),
            )

    def courses(self) -> list[dict[str, Any]]:
        """All saved courses. The library has no course methods, so this uses the
        generic authenticated passthrough against Garmin's course service."""
        with _mapped_errors():
            return cast(list[dict[str, Any]], self._api.connectapi("/course-service/course"))

    # --- per-activity detail (all read-only) ---

    def activity_summary(self, activity_id: str) -> dict[str, Any]:
        with _mapped_errors():
            return cast(dict[str, Any], self._api.get_activity(activity_id))

    def activity_splits(self, activity_id: str) -> dict[str, Any]:
        with _mapped_errors():
            return cast(dict[str, Any], self._api.get_activity_splits(activity_id))

    def activity_hr_zones(self, activity_id: str) -> list[dict[str, Any]]:
        with _mapped_errors():
            return cast(list[dict[str, Any]], self._api.get_activity_hr_in_timezones(activity_id))

    def activity_power_zones(self, activity_id: str) -> list[dict[str, Any]]:
        with _mapped_errors():
            return cast(
                list[dict[str, Any]],
                self._api.get_activity_power_in_timezones(activity_id),
            )

    def activity_details(self, activity_id: str, max_points: int = 150) -> dict[str, Any]:
        with _mapped_errors():
            return cast(
                dict[str, Any],
                self._api.get_activity_details(activity_id, maxchart=max_points, maxpoly=10),
            )

    # --- recovery / physiology (per calendar date YYYY-MM-DD) ---

    def training_status(self, cdate: str) -> dict[str, Any]:
        with _mapped_errors():
            return cast(dict[str, Any], self._api.get_training_status(cdate))

    def training_readiness(self, cdate: str) -> list[dict[str, Any]]:
        with _mapped_errors():
            return cast(list[dict[str, Any]], self._api.get_training_readiness(cdate))

    def hrv_daily(self, cdate: str) -> dict[str, Any] | None:
        with _mapped_errors():
            return cast(dict[str, Any] | None, self._api.get_hrv_data(cdate))

    def sleep_daily(self, cdate: str) -> dict[str, Any]:
        with _mapped_errors():
            return cast(dict[str, Any], self._api.get_sleep_data(cdate))

    def rhr_daily(self, cdate: str) -> dict[str, Any]:
        with _mapped_errors():
            return cast(dict[str, Any], self._api.get_rhr_day(cdate))

    def max_metrics(self, cdate: str) -> list[dict[str, Any]] | dict[str, Any]:
        with _mapped_errors():
            return cast(list[dict[str, Any]] | dict[str, Any], self._api.get_max_metrics(cdate))

    def fitness_age(self, cdate: str) -> dict[str, Any]:
        with _mapped_errors():
            return cast(dict[str, Any], self._api.get_fitnessage_data(cdate))

    def cycling_ftp(self) -> dict[str, Any]:
        with _mapped_errors():
            return cast(dict[str, Any], self._api.get_cycling_ftp())
