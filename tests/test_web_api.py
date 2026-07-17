import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_server import FakeGarminClient, install_fake  # reuse fixtures

from garmin_coach import server
from garmin_coach.auth import REAUTH_MESSAGE
from garmin_coach.client import ReauthRequiredError
from garmin_coach.web.app import create_app

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(autouse=True)
def reset_client_cache():
    server._drop_client()
    yield
    server._drop_client()


@pytest.fixture
def web() -> TestClient:
    return TestClient(create_app())


def test_rides_endpoint_returns_normalized(web: TestClient, monkeypatch: pytest.MonkeyPatch):
    install_fake(monkeypatch, FakeGarminClient(load("activity_list.json")))
    resp = web.get("/api/rides?limit=5")
    assert resp.status_code == 200
    rides = resp.json()
    assert rides[0]["distance_km"] == 46.28
    assert rides[0]["source"] == "garmin"


def test_weekly_endpoint(web: TestClient, monkeypatch: pytest.MonkeyPatch):
    fake = FakeGarminClient([])
    fake.canned["cycling_activities_by_date"] = load("activity_list.json")
    install_fake(monkeypatch, fake)
    resp = web.get("/api/weekly?weeks=2")
    assert resp.status_code == 200
    assert len(resp.json()["weeks"]) == 2


def test_reauth_maps_to_401(web: TestClient, monkeypatch: pytest.MonkeyPatch):
    install_fake(monkeypatch, FakeGarminClient(ReauthRequiredError(REAUTH_MESSAGE)))
    resp = web.get("/api/rides")
    assert resp.status_code == 401
    assert "garmin-setup" in resp.json()["detail"]


def test_status_endpoint_bundles_metrics(web: TestClient, monkeypatch: pytest.MonkeyPatch):
    fake = FakeGarminClient([])
    fake.canned["training_status"] = load("training_status.json")
    fake.canned["cycling_ftp"] = load("cycling_ftp.json")
    fake.canned["max_metrics"] = load("max_metrics.json")
    fake.canned["fitness_age"] = load("fitness_age.json")
    install_fake(monkeypatch, fake)
    resp = web.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ftp"]["ftp_w"] == 290.0
    assert body["training_status"]["acwr_status"] == "OPTIMAL"


def test_courses_endpoint(web: TestClient, monkeypatch: pytest.MonkeyPatch):
    fake = FakeGarminClient([])
    fake.canned["courses"] = load("courses.json")
    install_fake(monkeypatch, fake)
    resp = web.get("/api/courses")
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()]
    assert "Afternoon Ride" in names


def test_sessions_endpoint_serves_structured_plan(web: TestClient):
    resp = web.get("/api/sessions")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["weeks"]) == 8
    week1 = body["weeks"][0]
    assert week1["start"] == "2026-07-20"
    assert all("id" in s and "title" in s and "kind" in s for s in week1["sessions"])
    race = body["weeks"][7]["sessions"][-1]
    assert race["fixed_date"] == "2026-09-12"


def test_plan_endpoint_serves_markdown(web: TestClient):
    resp = web.get("/api/plan")
    assert resp.status_code == 200
    body = resp.json()
    assert "Whistler" in body["markdown"]
