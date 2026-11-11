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
    assert detail["runtime"] == []
    assert detail["externalCapabilities"] == []
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


def test_readiness_api_returns_separate_runtime_and_external_capabilities(
    tmp_path, monkeypatch
):
    runtime = [{
        "id": "runtime.python",
        "category": "core",
        "capability": "Python environment",
        "status": "ready",
        "required": True,
        "impact": "Python is available.",
        "correctiveAction": "No action required.",
        "checkedAt": "2099-12-31T00:00:00Z",
    }]
    external = [{
        "id": "external.aiProvider",
        "category": "external",
        "capability": "AI inference provider (not configured)",
        "status": "notConfigured",
        "installationStatus": "notConfigured",
        "required": False,
        "impact": "The Assistant is unavailable.",
        "correctiveAction": "Set NOC_WEB_AI_PROVIDER.",
        "checkedAt": "2099-12-31T00:00:00Z",
        "configuredProvider": None,
        "model": None,
        "providerReadiness": "notConfigured",
    }, {
        "id": "external.atlas",
        "category": "external",
        "capability": "Atlas Jira access",
        "status": "setup_required",
        "required": False,
        "impact": "Jira refresh is unavailable.",
        "correctiveAction": "Install and authenticate Atlas.",
        "checkedAt": "2099-12-31T00:00:00Z",
    }]
    monkeypatch.setattr(readiness_api, "resolve_readiness_profile", lambda: _profile(tmp_path))
    monkeypatch.setattr(
        readiness_api,
        "assess_readiness",
        lambda *_args: {
            "assessedAt": "2099-12-31T00:00:00Z",
            "shiftDate": "2099-12-31",
            "overallStatus": "ready",
            "readOnly": True,
            "configuration": {"id": "configuration.profile", "status": "ready"},
            "checks": [],
            "liveness": [],
        },
    )
    monkeypatch.setattr(readiness_api, "assess_runtime_readiness", lambda: runtime)
    monkeypatch.setattr(
        readiness_api,
        "assess_external_capabilities",
        lambda *_args, **_kwargs: external,
    )

    response = TestClient(app).get("/api/readiness/2099-12-31")

    assert response.status_code == 200
    assert response.json()["runtime"] == runtime
    assert response.json()["externalCapabilities"] == external
    assert response.json()["overallStatus"] == "ready"


def test_root_health_reports_static_provider_state_without_secrets(monkeypatch):
    sentinel = "test-sentinel-deepseek-key"
    monkeypatch.setenv("NOC_WEB_AI_PROVIDER", "deepseek-api")
    monkeypatch.setenv("NOC_WEB_DEEPSEEK_API_KEY", sentinel)
    monkeypatch.setenv("NOC_WEB_DEEPSEEK_MODEL", "deepseek-flash")

    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    ai_provider = response.json()["aiProvider"]
    assert ai_provider["configuredProvider"] == "deepseek-api"
    assert ai_provider["readiness"] == "ready"
    assert ai_provider["label"] == "DeepSeek API"
    assert ai_provider["model"] == "deepseek-flash"
    assert ai_provider["primaryProvider"]["configuredProvider"] == "deepseek-api"
    assert ai_provider["primaryProvider"]["readiness"] == "ready"
    assert ai_provider["localProvider"]["configuredProvider"] == "ollama"
    assert ai_provider["localProvider"]["readiness"] == "notConfigured"
    assert sentinel not in response.text

    monkeypatch.delenv("NOC_WEB_AI_PROVIDER", raising=False)
    not_configured = TestClient(app).get("/api/health").json()["aiProvider"]
    assert not_configured["readiness"] == "notConfigured"
    assert not_configured["configuredProvider"] is None


def test_shift_health_ai_provider_section_is_warning_only(tmp_path, monkeypatch):
    from backend.services import health as health_service

    class _Result:
        returncode = 0

    monkeypatch.setattr(health_service, "NOC_ROOT", tmp_path)
    monkeypatch.setattr(
        health_service.shutil,
        "which",
        lambda command: f"/usr/bin/{command}",
    )
    monkeypatch.setattr(
        health_service.subprocess,
        "run",
        lambda *args, **kwargs: _Result(),
    )
    monkeypatch.setenv("NOC_WEB_AI_PROVIDER", "deepseek-api")
    monkeypatch.setenv("NOC_WEB_DEEPSEEK_API_KEY", "test-sentinel-deepseek-key")

    ready = health_service.get_health("2099-12-31")
    ready_checks = [
        check for check in ready["checks"] if check["section"] == "AI Provider"
    ]
    assert len(ready_checks) == 1
    assert ready_checks[0]["state"] == "pass"
    assert ready["aiProvider"]["primaryProvider"]["configuredProvider"] == "deepseek-api"
    assert ready["aiProvider"]["primaryProvider"]["readiness"] == "ready"
    assert ready["aiProvider"]["localProvider"]["readiness"] == "notConfigured"
    assert "test-sentinel-deepseek-key" not in str(ready)

    monkeypatch.setenv("NOC_WEB_AI_PROVIDER", "unsupported-provider")
    not_ready = health_service.get_health("2099-12-31")
    not_ready_checks = [
        check for check in not_ready["checks"] if check["section"] == "AI Provider"
    ]
    assert not_ready_checks[0]["state"] == "warning"
    assert "unsupported-provider" not in str(not_ready)

    monkeypatch.delenv("NOC_WEB_AI_PROVIDER", raising=False)
    not_configured = health_service.get_health("2099-12-31")
    unconfigured_checks = [
        check for check in not_configured["checks"] if check["section"] == "AI Provider"
    ]
    assert unconfigured_checks[0]["state"] == "warning"


def test_root_health_reports_static_datadog_provider_without_secrets(monkeypatch):
    sentinel = "test-sentinel-datadog-token"
    monkeypatch.setenv("NOC_WEB_DATADOG_ACCESS_TOKEN", sentinel)
    monkeypatch.setenv("NOC_WEB_DATADOG_BASE_URL", "https://api.datadoghq.com")

    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    datadog = response.json()["datadogProvider"]
    assert datadog["provider"] == "datadog-api"
    assert datadog["configuredProvider"] == "datadog-api"
    assert datadog["readiness"] == "ready"
    assert datadog["credentialPresent"] is True
    assert datadog["baseUrl"] == "https://api.datadoghq.com"
    assert sentinel not in response.text

    monkeypatch.delenv("NOC_WEB_DATADOG_ACCESS_TOKEN", raising=False)
    not_configured = TestClient(app).get("/api/health").json()["datadogProvider"]
    assert not_configured["readiness"] == "notConfigured"
    assert not_configured["configuredProvider"] is None
