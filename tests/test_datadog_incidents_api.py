import multiprocessing
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import app
from backend.services import datadog_incidents


def _incident(identifier="incident-1"):
    return {
        "id": identifier,
        "title": "Customer Platform latency",
        "state": "active",
        "severity": "SEV-2",
    }


def _hold_refresh_in_process(cache_file, provider_started, release_provider, results):
    def provider():
        provider_started.set()
        if not release_provider.wait(timeout=8):
            raise RuntimeError("test provider was not released")
        return {"incidents": [_incident()]}

    snapshot = datadog_incidents.request_refresh(
        cache_file=cache_file,
        provider=provider,
    )
    results.put(snapshot["freshness"])
    if not release_provider.wait(timeout=8):
        raise RuntimeError("test provider was not released")
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        snapshot = datadog_incidents.get_incident_snapshot(
            cache_file,
            schedule_refresh=False,
        )
        if snapshot["freshness"] == "current":
            return
        time.sleep(0.01)
    raise RuntimeError("test provider did not finish")


def test_dashboard_and_investigations_share_same_incident_snapshot(
    noc_root,
    monkeypatch,
):
    cache_file = noc_root / ".datadog-active-incidents.json"
    snapshot = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: {"incidents": [_incident()]},
        now=datetime(2026, 10, 30, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(
        datadog_incidents,
        "get_cache_file",
        lambda: cache_file,
    )
    monkeypatch.setattr(
        datadog_incidents,
        "schedule_refresh_if_due",
        lambda *args, **kwargs: None,
    )

    client = TestClient(app)
    dashboard = client.get("/api/datadog/incidents")
    investigations = client.get("/api/datadog/incidents")

    assert dashboard.status_code == 200
    assert investigations.status_code == 200
    assert dashboard.json() == investigations.json()
    assert dashboard.json()["incidents"] == snapshot["incidents"]


def test_get_reports_refreshing_while_another_worker_holds_refresh_lock(
    tmp_path,
    monkeypatch,
):
    context = multiprocessing.get_context("spawn")
    cache_file = tmp_path / "incidents.json"
    provider_started = context.Event()
    release_provider = context.Event()
    results = context.Queue()
    monkeypatch.setattr(datadog_incidents, "get_cache_file", lambda: cache_file)
    worker = context.Process(
        target=_hold_refresh_in_process,
        args=(
            str(cache_file),
            provider_started,
            release_provider,
            results,
        ),
    )

    worker.start()
    try:
        assert provider_started.wait(timeout=8)
        assert results.get(timeout=8) == "refreshing"

        response = TestClient(app).get("/api/datadog/incidents")

        assert response.status_code == 200
        assert response.json()["freshness"] == "refreshing"
    finally:
        release_provider.set()
        worker.join(timeout=8)

    assert worker.exitcode == 0


def test_cache_read_is_nonblocking_and_does_not_run_provider_inline(
    noc_root,
    monkeypatch,
):
    cache_file = noc_root / ".datadog-active-incidents.json"
    snapshot = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: {"incidents": [_incident()]},
        now=datetime.now(timezone.utc),
    )
    monkeypatch.setattr(
        datadog_incidents,
        "get_cache_file",
        lambda: cache_file,
    )
    scheduled = []
    monkeypatch.setattr(
        datadog_incidents,
        "schedule_refresh_if_due",
        lambda *args, **kwargs: scheduled.append(kwargs),
    )
    monkeypatch.setattr(
        datadog_incidents,
        "retrieve_active_incidents",
        lambda: (_ for _ in ()).throw(AssertionError("provider ran inline")),
    )

    response = TestClient(app).get("/api/datadog/incidents")

    assert response.status_code == 200
    assert response.json()["incidents"] == snapshot["incidents"]
    assert len(scheduled) == 1


def test_manual_refresh_schedules_shared_refresh_without_request_payload(
    noc_root,
    monkeypatch,
):
    cache_file = noc_root / ".datadog-active-incidents.json"
    monkeypatch.setattr(
        datadog_incidents,
        "get_cache_file",
        lambda: cache_file,
    )
    scheduled = []
    monkeypatch.setattr(
        datadog_incidents,
        "request_refresh",
        lambda **kwargs: scheduled.append(kwargs)
        or datadog_incidents.get_incident_snapshot(
            cache_file,
            schedule_refresh=False,
        ),
    )

    response = TestClient(app).post("/api/datadog/incidents/refresh")

    assert response.status_code == 200
    assert response.json()["freshness"] == "unavailable"
    assert scheduled == [{}]


def test_api_distinguishes_unavailable_from_successful_empty_snapshot(
    noc_root,
    monkeypatch,
):
    cache_file = noc_root / ".datadog-active-incidents.json"
    monkeypatch.setattr(
        datadog_incidents,
        "get_cache_file",
        lambda: cache_file,
    )
    monkeypatch.setattr(
        datadog_incidents,
        "schedule_refresh_if_due",
        lambda *args, **kwargs: None,
    )
    client = TestClient(app)

    unavailable = client.get("/api/datadog/incidents").json()
    assert unavailable["freshness"] == "unavailable"
    assert unavailable["count"] is None

    datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: {"incidents": []},
        now=datetime.now(timezone.utc),
    )
    empty_success = client.get("/api/datadog/incidents").json()
    assert empty_success["freshness"] == "current"
    assert empty_success["count"] == 0
    assert empty_success["incidents"] == []


def test_resolved_incident_refresh_does_not_change_local_history_or_handover(
    noc_root,
    monkeypatch,
):
    investigation = (
        noc_root
        / "2026-10-30"
        / "investigations"
        / "reviewed-incident"
        / "reviewed-context.json"
    )
    investigation.parent.mkdir(parents=True)
    investigation.write_text(
        '{"reviewState":"reviewed","finding":"Operator finding","state":"Active"}',
        encoding="utf-8",
    )
    handover = noc_root / "2026-10-30" / "handover" / "handover-2026-10-30.md"
    handover.parent.mkdir()
    handover.write_text("Operator-authored handover\n", encoding="utf-8")
    cache_file = noc_root / ".datadog-active-incidents.json"
    monkeypatch.setattr(
        datadog_incidents,
        "get_cache_file",
        lambda: cache_file,
    )
    monkeypatch.setattr(
        datadog_incidents,
        "request_refresh",
        lambda **kwargs: datadog_incidents.refresh_incident_cache(
            cache_file,
            provider=lambda: {
                "incidents": [
                    {**_incident(), "state": "RESOLVED"},
                ]
            },
        ),
    )

    response = TestClient(app).post("/api/datadog/incidents/refresh")

    assert response.status_code == 200
    assert response.json()["freshness"] == "current"
    assert response.json()["error"] is None
    assert response.json()["incidents"] == []
    assert investigation.read_text(encoding="utf-8") == (
        '{"reviewState":"reviewed","finding":"Operator finding","state":"Active"}'
    )
    assert handover.read_text(encoding="utf-8") == "Operator-authored handover\n"


def test_due_automatic_refresh_uses_same_read_only_cache_service(
    noc_root,
    monkeypatch,
):
    cache_file = noc_root / ".datadog-active-incidents.json"
    now = datetime.now(timezone.utc)
    calls = []

    def refresh(**kwargs):
        calls.append(kwargs)
        return datadog_incidents.refresh_incident_cache(
            cache_file,
            provider=lambda: {"incidents": [_incident()]},
            now=now,
        )

    monkeypatch.setattr(
        datadog_incidents,
        "get_cache_file",
        lambda: cache_file,
    )
    monkeypatch.setattr(datadog_incidents, "request_refresh", refresh)

    snapshot = datadog_incidents.get_incident_snapshot(now=now)

    assert snapshot["incidents"] == [_incident()]
    assert snapshot["freshness"] == "current"
    assert len(calls) == 1


def test_automatic_resolved_refresh_preserves_local_investigation_and_handover(
    noc_root,
    monkeypatch,
):
    investigation = (
        noc_root
        / "2026-10-30"
        / "investigations"
        / "reviewed-incident"
        / "reviewed-context.json"
    )
    investigation.parent.mkdir(parents=True)
    review_record = (
        '{"reviewState":"reviewed","finding":"Operator finding","state":"Active"}'
    )
    investigation.write_text(review_record, encoding="utf-8")
    handover = noc_root / "2026-10-30" / "handover" / "handover-2026-10-30.md"
    handover.parent.mkdir()
    handover.write_text("Operator-authored handover\n", encoding="utf-8")
    cache_file = noc_root / ".datadog-active-incidents.json"
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(
        datadog_incidents,
        "get_cache_file",
        lambda: cache_file,
    )
    monkeypatch.setattr(
        datadog_incidents,
        "schedule_refresh_if_due",
        lambda path, **kwargs: datadog_incidents.refresh_incident_cache(
            path,
            provider=lambda: {
                "incidents": [{**_incident(), "state": "RESOLVED"}],
            },
            now=now,
        ),
    )

    snapshot = datadog_incidents.get_incident_snapshot(now=now)

    assert snapshot["freshness"] == "current"
    assert snapshot["incidents"] == []
    assert investigation.read_text(encoding="utf-8") == review_record
    assert handover.read_text(encoding="utf-8") == "Operator-authored handover\n"


def test_incident_routes_publish_shared_response_schema():
    schema = app.openapi()
    get_response = schema["paths"]["/api/datadog/incidents"]["get"]["responses"][
        "200"
    ]["content"]["application/json"]["schema"]
    post_response = schema["paths"]["/api/datadog/incidents/refresh"]["post"][
        "responses"
    ]["200"]["content"]["application/json"]["schema"]

    assert get_response == post_response
    snapshot_schema = schema["components"]["schemas"]["IncidentSnapshotResponse"]
    assert set(snapshot_schema["properties"]) == {
        "incidents",
        "count",
        "lastAttemptedAt",
        "lastSuccessfulAt",
        "freshness",
        "error",
    }
    assert set(snapshot_schema["required"]) == set(snapshot_schema["properties"])
    freshness_schema = snapshot_schema["properties"]["freshness"]
    assert freshness_schema["enum"] == [
        "current",
        "stale",
        "unavailable",
        "refreshing",
    ]
    incident_ref = snapshot_schema["properties"]["incidents"]["items"]["$ref"]
    assert incident_ref == "#/components/schemas/IncidentProjectionResponse"
    incident_schema = schema["components"]["schemas"][
        "IncidentProjectionResponse"
    ]
    assert set(incident_schema["properties"]) == {
        "id",
        "title",
        "state",
        "severity",
        "createdAt",
        "updatedAt",
        "summary",
        "url",
    }
