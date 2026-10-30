from fastapi.testclient import TestClient

from backend.app import app
from backend.config import CacheSourcePolicy, ConfigurationError, ConfigurationProfile
from backend.api import readiness as readiness_api


def _profile(tmp_path):
    root = tmp_path / "noc"
    root.mkdir()
    return ConfigurationProfile(
        noc_root=root,
        noc_bin=root,
        probe_directory=root,
        cache_sources=(CacheSourcePolicy("jiraOpenTickets", 60),),
        command_timeout_seconds=1,
        settings=(),
    )


def test_invalid_shift_date_returns_400():
    response = TestClient(app).get("/api/readiness/not-a-date")
    assert response.status_code == 400


def test_invalid_explicit_configuration_stops_all_probes(monkeypatch):
    called = False

    def invalid_profile():
        raise ConfigurationError("NOC_WEB_NOC_ROOT", explicit=True)

    def assessment(*args):
        nonlocal called
        called = True

    monkeypatch.setattr(readiness_api, "resolve_readiness_profile", invalid_profile)
    monkeypatch.setattr(readiness_api, "assess_readiness", assessment)
    response = TestClient(app).get("/api/readiness/2099-12-31")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["checks"] == []
    assert detail["liveness"] == []
    assert detail["configuration"]["id"] == "configuration.NOC_WEB_NOC_ROOT"
    assert called is False


def test_failed_assessment_is_http_200_and_contract_is_read_only(tmp_path, monkeypatch):
    result = {
        "assessedAt": "2099-12-31T00:00:00Z",
        "shiftDate": "2099-12-31",
        "overallStatus": "notReady",
        "readOnly": True,
        "configuration": {"id": "configuration.profile", "status": "ready"},
        "checks": [{"id": "writeCapability.probe", "status": "notReady"}],
        "liveness": [{"id": "liveness.jira", "status": "available"}],
    }
    monkeypatch.setattr(readiness_api, "resolve_readiness_profile", lambda: _profile(tmp_path))
    monkeypatch.setattr(readiness_api, "assess_readiness", lambda profile, shift: result)

    response = TestClient(app).get("/api/readiness/2099-12-31")

    assert response.status_code == 200
    assert response.json() == result
    assert response.json()["liveness"][0]["status"] == "available"


def test_readiness_client_and_page_are_read_only():
    api = (app.root_path and "")  # Keep this test independent of a served browser.
    from pathlib import Path

    root = Path(__file__).parents[1]
    client = (root / "frontend" / "js" / "api.js").read_text(encoding="utf-8")
    page = (root / "frontend" / "readiness.html").read_text(encoding="utf-8")
    assert "getReadiness" in client
    assert "method:" not in page
    assert "Readiness page may render" not in page
