import json
from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from garmin_coach import server
from garmin_coach.auth import REAUTH_MESSAGE
from garmin_coach.client import ReauthRequiredError

FIXTURES = Path(__file__).parent / "fixtures"


class FakeGarminClient:
    """Stands in for GarminClient; no network."""

    def __init__(self, activities: list[dict[str, Any]] | Exception) -> None:
        self._activities = activities
        self.last_limit: int | None = None
        self.canned: dict[str, Any] = {}
        self.calls: list[str] = []

    def recent_cycling_activities(self, limit: int = 5) -> list[dict[str, Any]]:
        self.last_limit = limit
        if isinstance(self._activities, Exception):
            raise self._activities
        return self._activities[:limit]

    def __getattr__(self, name: str) -> Any:
        if name not in self.canned:
            raise AttributeError(name)

        def method(*args: Any, **kwargs: Any) -> Any:
            self.calls.append(name)
            value = self.canned[name]
            if isinstance(value, Exception):
                raise value
            return value

        return method


@pytest.fixture(autouse=True)
def reset_client_cache():
    server._drop_client()
    yield
    server._drop_client()


def install_fake(monkeypatch: pytest.MonkeyPatch, fake: FakeGarminClient) -> None:
    monkeypatch.setattr(server, "_cached_client", fake)


def load_fixture() -> list[dict[str, Any]]:
    return json.loads((FIXTURES / "activity_list.json").read_text())


def test_tool_returns_normalized_dicts(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake(monkeypatch, FakeGarminClient(load_fixture()))

    rides = server.get_recent_activities(limit=5)

    assert len(rides) == 2
    first = rides[0]
    assert first["distance_km"] == 46.28
    assert first["normalized_power_w"] == 204.0
    assert first["source"] == "garmin"
    assert "single-sided" in first["power_note"]
    # raw Garmin keys must not leak through
    assert "activityName" not in first and "startTimeGMT" not in first


def test_limit_is_clamped(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGarminClient(load_fixture())
    install_fake(monkeypatch, fake)

    server.get_recent_activities(limit=0)
    assert fake.last_limit == 1
    server.get_recent_activities(limit=999)
    assert fake.last_limit == server.MAX_LIMIT


def test_reauth_error_is_actionable_and_drops_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake(monkeypatch, FakeGarminClient(ReauthRequiredError(REAUTH_MESSAGE)))

    with pytest.raises(RuntimeError, match="garmin-setup"):
        server.get_recent_activities()
    # cache dropped so a later call can pick up fresh tokens
    assert server._cached_client is None


EXPECTED_TOOLS = {
    "get_recent_activities",
    "get_activity_summary",
    "get_activity_splits",
    "get_activity_power_data",
    "get_activity_heart_rate_data",
    "get_activity_details",
    "compare_activities",
    "get_training_status",
    "get_training_readiness",
    "get_recovery_time",
    "get_hrv_history",
    "get_sleep_history",
    "get_resting_heart_rate_history",
    "get_vo2_max",
    "get_current_ftp",
}


def test_mcp_protocol_lists_all_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake(monkeypatch, FakeGarminClient(load_fixture()))

    async def run() -> None:
        async with create_connected_server_and_client_session(server.mcp) as session:
            tools = await session.list_tools()
            assert {t.name for t in tools.tools} == EXPECTED_TOOLS

            result = await session.call_tool("get_recent_activities", {"limit": 2})
            assert not result.isError
            payload = json.loads(result.content[0].text)
            ride = payload[0] if isinstance(payload, list) else payload
            assert ride["activity_id"] == 100000001

    anyio.run(run)


def load_json(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


def test_recovery_time_reports_unavailable_without_watch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeGarminClient([])
    fake.canned["training_readiness"] = []
    install_fake(monkeypatch, fake)

    result = server.get_recovery_time("2026-07-16")
    assert result["available"] is False
    assert result["recovery_time_h"] is None
    assert "not exposed" in result["note"]


def test_recovery_time_extracted_from_readiness(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGarminClient([])
    fake.canned["training_readiness"] = [{"score": 61, "recoveryTime": 18, "level": "MODERATE"}]
    install_fake(monkeypatch, fake)

    result = server.get_recovery_time("2026-07-16")
    assert result["available"] is True
    assert result["recovery_time_h"] == 18.0


def test_hrv_history_separates_missing_days(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGarminClient([])
    fake.canned["hrv_daily"] = load_json("hrv_data.json")
    install_fake(monkeypatch, fake)

    result = server.get_hrv_history(days=3, end_date="2026-07-16")
    assert len(result["days"]) == 3  # same canned payload for each date
    assert result["missing_dates"] == []
    assert len(fake.calls) == 3


def test_sleep_history_lists_unrecorded_nights(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGarminClient([])
    fake.canned["sleep_daily"] = {"dailySleepDTO": {"sleepTimeSeconds": None}}
    install_fake(monkeypatch, fake)

    result = server.get_sleep_history(days=2, end_date="2026-07-16")
    assert result["nights"] == []
    assert result["missing_dates"] == ["2026-07-15", "2026-07-16"]


def test_invalid_date_raises_readable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake(monkeypatch, FakeGarminClient([]))
    with pytest.raises(RuntimeError, match="YYYY-MM-DD"):
        server.get_training_status("July 16th")


def test_history_days_clamped_to_max(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGarminClient([])
    fake.canned["rhr_daily"] = load_json("rhr_day.json")
    install_fake(monkeypatch, fake)

    result = server.get_resting_heart_rate_history(days=99, end_date="2026-07-16")
    assert len(fake.calls) == server.MAX_HISTORY_DAYS
    assert len(result["days"]) == server.MAX_HISTORY_DAYS
