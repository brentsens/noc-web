import json
import shutil
import subprocess

from fastapi.testclient import TestClient

from backend.app import app
from backend.services import (
    copilot_cli,
    datadog_incidents,
    handover_delivery,
    jira_discovery,
    ticket_sync,
    tickets,
)
from backend.services.copilot_mcp import CopilotProviderUnavailable
from backend.services.datadog_provider import (
    DatadogClient,
    DatadogConfiguration,
    DatadogProviderUnavailable,
)


client = TestClient(app)


def test_missing_atlas_returns_safe_dependency_error_without_blocking_local_tickets(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(jira_discovery.shutil, "which", lambda _command: None)
    ticket_directory = tmp_path / "tickets" / "open"
    ticket_directory.mkdir(parents=True)
    (ticket_directory / "NOC-111.json").write_text(
        json.dumps({
            "id": "NOC-111",
            "jira": {"summary": "Local record"},
            "noc": {"next_action": "Continue locally"},
            "metadata": {},
            "tracking": {"state": "active"},
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        tickets,
        "_ticket_dir",
        lambda state="open": (
            ticket_directory if state == "open" else tmp_path / "closed"
        ),
    )

    jira_response = client.get("/api/jira/tickets")
    local_response = client.get("/api/tickets")

    assert jira_response.status_code == 503
    assert jira_response.json()["detail"]["code"] == "atlas-unavailable"
    assert local_response.status_code == 200
    assert local_response.json()["tickets"][0]["id"] == "NOC-111"


def test_atlas_error_output_is_not_returned_to_api(monkeypatch):
    secret = "JIRA-CONTENT-SECRET-FIXTURE"
    monkeypatch.setattr(jira_discovery.shutil, "which", lambda _command: "/mock/atlas")
    monkeypatch.setattr(
        jira_discovery.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0], returncode=1, stdout=secret, stderr=secret
        ),
    )

    response = client.get("/api/jira/tickets")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "atlas-operation-failed"
    assert secret not in response.text


def test_missing_copilot_fails_without_fallback_provider(monkeypatch):
    monkeypatch.setattr(copilot_cli.shutil, "which", lambda _command: None)
    monkeypatch.setattr(
        copilot_cli.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("no alternate provider may be invoked")
        ),
    )

    try:
        copilot_cli.answer_with_copilot_cli({"question": "test"})
        raise AssertionError("missing Copilot must be explicit")
    except CopilotProviderUnavailable as error:
        assert error.provider_invoked is False
        assert "not installed" in str(error).lower()


def test_datadog_refresh_failure_preserves_previous_incident_cache(tmp_path):
    cache_file = tmp_path / "incidents.json"
    previous = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: {
            "incidents": [{
                "id": "incident-1",
                "title": "Existing incident",
                "state": "active",
            }]
        },
    )

    def missing_datadog_mcp():
        raise datadog_incidents.IncidentRefreshFailure("provider-unavailable")

    refreshed = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=missing_datadog_mcp,
    )

    assert refreshed["freshness"] == "stale"
    assert refreshed["incidents"] == previous["incidents"]


def test_missing_microsoft_365_is_explicit_and_local_handover_is_unaffected(
    tmp_path, monkeypatch
):
    handover_directory = tmp_path / "2099-12-31" / "handover"
    handover_directory.mkdir(parents=True)
    (handover_directory / "handover-2099-12-31.md").write_text(
        "Local handover content", encoding="utf-8"
    )
    monkeypatch.setattr(handover_delivery, "NOC_ROOT", tmp_path)
    monkeypatch.setattr(handover_delivery.shutil, "which", lambda _command: None)

    response = client.post(
        "/api/shifts/2099-12-31/handover/preview",
        json={},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "microsoft365-unavailable"
    assert (handover_directory / "handover-2099-12-31.md").is_file()


def test_missing_noc_tools_returns_safe_unavailable_without_changing_local_records(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(ticket_sync.shutil, "which", lambda _command: None)

    response = client.post("/api/ticket-sync/sync")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "noc-tools-unavailable"


def test_datadog_direct_provider_failure_preserves_cache_without_copilot_or_mcp(
    tmp_path,
    fake_datadog_transport,
    monkeypatch,
):
    cache_file = tmp_path / "incidents.json"
    previous = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: {
            "incidents": [{
                "id": "incident-1",
                "title": "Existing incident",
                "state": "active",
            }]
        },
    )
    fake_datadog_transport.add_error(
        DatadogProviderUnavailable("unavailable")
    )
    client = DatadogClient(
        DatadogConfiguration(
            base_url="https://api.datadoghq.com",
            timeout_seconds=90,
            credential_present=True,
        ),
        "test-sentinel-datadog-token",
        transport=fake_datadog_transport,
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Copilot must not be invoked")
        ),
    )
    monkeypatch.setattr(
        shutil,
        "which",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("MCP/Copilot lookup must not occur")
        ),
    )

    refreshed = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: datadog_incidents.retrieve_active_incidents(
            client=client
        ),
    )

    assert refreshed["freshness"] == "stale"
    assert refreshed["error"] == "provider-unavailable"
    assert refreshed["incidents"] == previous["incidents"]
