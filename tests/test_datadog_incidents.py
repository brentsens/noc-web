import json
import multiprocessing
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
import threading
import time

import pytest

from backend.services import datadog_incidents
from backend.services.datadog_provider import (
    DatadogConfiguration,
    DatadogClient,
    DatadogProviderTimeout,
    DatadogProviderUnavailable,
    DatadogResponse,
    MAX_RESPONSE_BYTES,
)


NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)


def _incident(identifier="incident-1", **overrides):
    return {
        "id": identifier,
        "title": f"Incident {identifier}",
        "state": "active",
        "severity": "SEV-2",
        "createdAt": "2026-10-30T11:14:00Z",
        "updatedAt": "2026-10-30T11:20:00Z",
        "summary": "Customer Platform latency",
        "url": "https://app.datadoghq.com/incidents/123",
        **overrides,
    }


def _search_incident(identifier="incident-1", state="ACTIVE", **attributes):
    values = {
        "title": f"Incident {identifier}",
        "state": state,
        "severity": "SEV-2",
        "created": "2026-10-30T11:14:00Z",
        "modified": "2026-10-30T11:20:00Z",
        "customer_impact_scope": "Customer Platform latency",
    }
    values.update(attributes)
    return {
        "data": {
            "id": identifier,
            "type": "incidents",
            "attributes": values,
        }
    }


def _search_payload(incidents, *, total=None, next_offset=None):
    payload = {
        "data": {
            "type": "incidents_search_results",
            "attributes": {
                "incidents": incidents,
                "total": len(incidents) if total is None else total,
            },
        }
    }
    if next_offset is not None:
        payload["meta"] = {
            "pagination": {
                "offset": 0,
                "size": 100,
                "next_offset": next_offset,
            }
        }
    return payload


def _direct_client(transport, base_url="https://api.datadoghq.com"):
    return DatadogClient(
        DatadogConfiguration(
            base_url=base_url,
            timeout_seconds=90,
            credential_present=True,
        ),
        "test-sentinel-datadog-token",
        transport=transport,
    )


def _process_refresh(
    cache_file,
    provider_started,
    release_provider,
    provider_calls,
    results,
    wait_for_completion,
):
    def provider():
        with provider_calls.get_lock():
            provider_calls.value += 1
        provider_started.set()
        if not release_provider.wait(timeout=8):
            raise RuntimeError("test provider was not released")
        return {"incidents": [_incident()]}

    snapshot = datadog_incidents.request_refresh(
        cache_file=cache_file,
        provider=provider,
    )
    results.put(snapshot["freshness"])
    if wait_for_completion:
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
    time.sleep(0.25)


def test_successful_refresh_persists_minimal_projection_for_multiple_incidents(tmp_path):
    cache_file = tmp_path / "incidents.json"

    snapshot = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: {"incidents": [_incident(), _incident("incident-2")]},
        now=NOW,
    )

    assert snapshot["freshness"] == "current"
    assert snapshot["count"] == 2
    assert [item["id"] for item in snapshot["incidents"]] == [
        "incident-1",
        "incident-2",
    ]
    persisted = json.loads(cache_file.read_text(encoding="utf-8"))
    assert persisted["incidents"] == snapshot["incidents"]
    assert "prompt" not in persisted
    assert "rawResponse" not in persisted
    assert "evidence" not in persisted


def test_refresh_accepts_exactly_100_active_incidents(tmp_path):
    incidents = [
        _incident(f"incident-{index}")
        for index in range(datadog_incidents.MAX_INCIDENTS)
    ]

    snapshot = datadog_incidents.refresh_incident_cache(
        tmp_path / "incidents.json",
        provider=lambda: {"incidents": incidents},
        now=NOW,
    )

    assert snapshot["freshness"] == "current"
    assert snapshot["count"] == 100
    assert len(snapshot["incidents"]) == 100


def test_refresh_over_100_incidents_preserves_previous_snapshot(tmp_path):
    cache_file = tmp_path / "incidents.json"
    original = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: {"incidents": [_incident()]},
        now=NOW,
    )
    oversized = [
        _incident(f"incident-{index}")
        for index in range(datadog_incidents.MAX_INCIDENTS + 1)
    ]

    failed = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: {"incidents": oversized},
        now=NOW + timedelta(seconds=10),
    )

    assert failed["freshness"] == "stale"
    assert failed["error"] == "invalid-response"
    assert failed["incidents"] == original["incidents"]
    assert failed["lastSuccessfulAt"] == original["lastSuccessfulAt"]
    persisted = json.loads(cache_file.read_text(encoding="utf-8"))
    assert persisted["incidents"] == original["incidents"]


def test_successful_empty_refresh_is_authoritative_and_resolved_incident_disappears(
    tmp_path,
):
    cache_file = tmp_path / "incidents.json"

    first = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: {"incidents": [_incident()]},
        now=NOW,
    )
    second = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: {"incidents": [_incident(state="resolved")]},
        now=NOW + timedelta(seconds=30),
    )

    assert first["incidents"] == [_incident()]
    assert second["freshness"] == "current"
    assert second["count"] == 0
    assert second["incidents"] == []
    assert second["lastSuccessfulAt"] != first["lastSuccessfulAt"]


@pytest.mark.parametrize(
    ("initial_state", "next_state", "expected_state"),
    [
        ("ACTIVE", "STABLE", "STABLE"),
        ("STABLE", "ACTIVE", "ACTIVE"),
        ("ACTIVE", "RESOLVED", None),
        ("STABLE", "RESOLVED", None),
    ],
)
def test_datadog_state_transitions_keep_current_incidents_until_resolved(
    tmp_path,
    initial_state,
    next_state,
    expected_state,
):
    cache_file = tmp_path / "incidents.json"

    initial = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: {"incidents": [_incident(state=initial_state)]},
        now=NOW,
    )
    updated = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: {"incidents": [_incident(state=next_state)]},
        now=NOW + timedelta(seconds=10),
    )

    assert initial["freshness"] == "current"
    assert initial["incidents"][0]["state"] == initial_state
    assert updated["freshness"] == "current"
    if expected_state is None:
        assert updated["incidents"] == []
    else:
        assert updated["incidents"][0]["state"] == expected_state


@pytest.mark.parametrize("state", ["ACTIVE", "STABLE"])
def test_failed_refresh_preserves_last_known_datadog_state_and_stales_cache(
    tmp_path,
    state,
):
    cache_file = tmp_path / "incidents.json"
    successful = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: {"incidents": [_incident(state=state)]},
        now=NOW,
    )

    failed = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: (_ for _ in ()).throw(RuntimeError("provider unavailable")),
        now=NOW + timedelta(seconds=10),
    )

    assert successful["freshness"] == "current"
    assert successful["incidents"][0]["state"] == state
    assert failed["freshness"] == "stale"
    assert failed["incidents"] == successful["incidents"]
    assert failed["incidents"][0]["state"] == state
    assert failed["lastSuccessfulAt"] == successful["lastSuccessfulAt"]


@pytest.mark.parametrize(
    "response",
    [
        [],
        {"incidents": "not-a-list"},
        {"incidents": [_incident(extra="unexpected")]},
        {"incidents": [_incident(state=[])]},
        {"incidents": [_incident(state="COMPLETED")]},
        {"incidents": [_incident("duplicate"), _incident("duplicate")]},
        {"incidents": [_incident(id="")]},
        {"incidents": [_incident(title="")]},
        {"incidents": [_incident(severity=2)]},
        {"incidents": [_incident(createdAt="not-a-timestamp")]},
        {"incidents": [_incident(url="https://datadoghq.com.attacker.invalid/incidents/1")]},
        {"incidents": [_incident(url="https://app.datadoghq.com:444/incidents/1")]},
        {"incidents": [_incident(url="https://app.datadoghq.com/incidents/../other")]},
        {"incidents": [_incident(id="i" * 129)]},
        {"incidents": [_incident(title="t" * 201)]},
        {"incidents": [_incident(severity="s" * 33)]},
        {"incidents": [_incident(summary="s" * 501)]},
        {"incidents": [_incident(createdAt="2" * 41)]},
        {"incidents": [_incident(url="https://app.datadoghq.com/incidents/" + "1" * 2048)]},
        {"incidents": [_incident()], "raw": "unexpected"},
    ],
)
def test_invalid_provider_output_fails_closed_and_preserves_previous_snapshot(
    tmp_path,
    response,
):
    cache_file = tmp_path / "incidents.json"
    original = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: {"incidents": [_incident()]},
        now=NOW,
    )

    failed = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: response,
        now=NOW + timedelta(seconds=10),
    )

    assert failed["freshness"] == "stale"
    assert failed["incidents"] == original["incidents"]
    assert failed["lastSuccessfulAt"] == original["lastSuccessfulAt"]
    assert failed["lastAttemptedAt"] != original["lastAttemptedAt"]
    assert failed["error"] == "invalid-response"


def test_first_refresh_failure_is_unavailable_not_successful_empty(tmp_path):
    snapshot = datadog_incidents.refresh_incident_cache(
        tmp_path / "missing-cache.json",
        provider=lambda: (_ for _ in ()).throw(RuntimeError("private provider error")),
        now=NOW,
    )

    assert snapshot["freshness"] == "unavailable"
    assert snapshot["incidents"] == []
    assert snapshot["count"] is None
    assert snapshot["lastSuccessfulAt"] is None
    assert snapshot["error"] == "provider-unavailable"


def test_old_successful_snapshot_becomes_stale_without_losing_timestamp(tmp_path):
    cache_file = tmp_path / "incidents.json"
    successful = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: {"incidents": [_incident()]},
        now=NOW,
    )

    snapshot = datadog_incidents.get_incident_snapshot(
        cache_file,
        now=NOW + timedelta(seconds=61),
        schedule_refresh=False,
    )

    assert snapshot["freshness"] == "stale"
    assert snapshot["incidents"] == successful["incidents"]
    assert snapshot["lastSuccessfulAt"] == successful["lastSuccessfulAt"]


def test_failed_cache_write_preserves_previous_successful_snapshot(
    tmp_path,
    monkeypatch,
):
    cache_file = tmp_path / "incidents.json"
    successful = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: {"incidents": [_incident()]},
        now=NOW,
    )

    def fail_replace(source, destination):
        raise OSError("private filesystem error")

    monkeypatch.setattr(datadog_incidents.os, "replace", fail_replace)
    failed = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: {"incidents": [_incident("incident-2")]},
        now=NOW + timedelta(seconds=10),
    )

    assert failed["freshness"] == "stale"
    assert failed["incidents"] == successful["incidents"]
    assert failed["lastSuccessfulAt"] == successful["lastSuccessfulAt"]


def test_concurrent_refresh_requests_coalesce_to_one_provider_call(tmp_path):
    cache_file = tmp_path / "incidents.json"
    started = threading.Event()
    release = threading.Event()
    calls = []

    def provider():
        calls.append(True)
        started.set()
        assert release.wait(timeout=2)
        return {"incidents": [_incident()]}

    first = datadog_incidents.request_refresh(
        cache_file=cache_file,
        provider=provider,
    )
    assert started.wait(timeout=2)
    second = datadog_incidents.request_refresh(
        cache_file=cache_file,
        provider=provider,
    )
    assert second["freshness"] == "refreshing"
    assert len(calls) == 1

    release.set()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        snapshot = datadog_incidents.get_incident_snapshot(
            cache_file,
            schedule_refresh=False,
        )
        if snapshot["freshness"] == "current":
            break
        time.sleep(0.01)

    assert first["freshness"] == "refreshing"
    assert snapshot["freshness"] == "current"
    assert len(calls) == 1


def test_refresh_requests_coalesce_across_processes_sharing_cache(tmp_path):
    context = multiprocessing.get_context("spawn")
    cache_file = str(tmp_path / "incidents.json")
    release_provider = context.Event()
    first_started = context.Event()
    second_started = context.Event()
    provider_calls = context.Value("i", 0)
    results = context.Queue()
    first = context.Process(
        target=_process_refresh,
        args=(
            cache_file,
            first_started,
            release_provider,
            provider_calls,
            results,
            True,
        ),
    )
    second = context.Process(
        target=_process_refresh,
        args=(
            cache_file,
            second_started,
            release_provider,
            provider_calls,
            results,
            False,
        ),
    )

    first.start()
    try:
        assert first_started.wait(timeout=8)
        second.start()
        assert results.get(timeout=8) == "refreshing"
        assert results.get(timeout=8) == "refreshing"
        assert not second_started.wait(timeout=0.25)
        with provider_calls.get_lock():
            assert provider_calls.value == 1
    finally:
        release_provider.set()
        first.join(timeout=8)
        if second.pid is not None:
            second.join(timeout=8)

    assert first.exitcode == 0
    assert second.exitcode == 0
    with provider_calls.get_lock():
        assert provider_calls.value == 1


def test_retrieve_active_incidents_maps_direct_search_without_copilot_or_mcp(
    fake_datadog_transport,
    monkeypatch,
):
    fake_datadog_transport.add_json(
        _search_payload(
            [
                _search_incident("incident-active", state="ACTIVE"),
                _search_incident("incident-stable", state="STABLE"),
                _search_incident("incident-resolved", state="RESOLVED"),
            ],
            total=3,
        )
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
            AssertionError("Copilot lookup must not occur")
        ),
    )

    result = datadog_incidents.retrieve_active_incidents(
        client=_direct_client(fake_datadog_transport)
    )

    assert [item["id"] for item in result["incidents"]] == [
        "incident-active",
        "incident-stable",
    ]
    assert [item["state"] for item in result["incidents"]] == ["ACTIVE", "STABLE"]
    assert result["incidents"][0]["url"] == (
        "https://app.datadoghq.com/incidents/incident-active"
    )
    assert fake_datadog_transport.calls[0]["method"] == "GET"


def test_retrieve_active_incidents_follows_bounded_pagination(
    fake_datadog_transport,
):
    first_page = [_search_incident(f"incident-{index}") for index in range(50)]
    second_page = [
        _search_incident(f"incident-{index}") for index in range(50, 100)
    ]
    fake_datadog_transport.add_json(
        _search_payload(first_page, total=100, next_offset=50)
    )
    fake_datadog_transport.add_json(_search_payload(second_page, total=100))

    result = datadog_incidents.retrieve_active_incidents(
        client=_direct_client(fake_datadog_transport)
    )

    assert len(result["incidents"]) == 100
    assert len(fake_datadog_transport.calls) == 2


def test_retrieve_active_incidents_rejects_more_than_100(
    fake_datadog_transport,
):
    fake_datadog_transport.add_json(
        _search_payload([_search_incident()], total=101)
    )

    with pytest.raises(datadog_incidents.IncidentResponseInvalid):
        datadog_incidents.retrieve_active_incidents(
            client=_direct_client(fake_datadog_transport)
        )


def test_retrieve_active_incidents_rejects_duplicate_ids(
    fake_datadog_transport,
):
    fake_datadog_transport.add_json(
        _search_payload(
            [_search_incident("duplicate"), _search_incident("duplicate")],
            total=2,
        )
    )

    with pytest.raises(datadog_incidents.IncidentResponseInvalid):
        datadog_incidents.retrieve_active_incidents(
            client=_direct_client(fake_datadog_transport)
        )


def test_retrieve_active_incidents_rejects_malformed_search_payload(
    fake_datadog_transport,
):
    fake_datadog_transport.add_json({
        "data": {"type": "incidents_search_results", "attributes": {"incidents": "bad"}}
    })

    with pytest.raises(datadog_incidents.IncidentResponseInvalid):
        datadog_incidents.retrieve_active_incidents(
            client=_direct_client(fake_datadog_transport)
        )


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (DatadogProviderTimeout("timed out"), "timeout"),
        (DatadogProviderUnavailable("unavailable"), "provider-unavailable"),
    ],
)
def test_provider_failure_maps_to_existing_codes_and_preserves_cache(
    tmp_path,
    fake_datadog_transport,
    error,
    expected_code,
):
    cache_file = tmp_path / "incidents.json"
    previous = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: {"incidents": [_incident()]},
        now=NOW,
    )
    fake_datadog_transport.add_error(error)

    failed = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: datadog_incidents.retrieve_active_incidents(
            client=_direct_client(fake_datadog_transport)
        ),
        now=NOW + timedelta(seconds=10),
    )

    assert failed["freshness"] == "stale"
    assert failed["error"] == expected_code
    assert failed["incidents"] == previous["incidents"]
    assert failed["lastSuccessfulAt"] == previous["lastSuccessfulAt"]


def test_direct_provider_first_refresh_failure_is_unavailable(
    tmp_path,
    fake_datadog_transport,
):
    fake_datadog_transport.add_error(
        DatadogProviderUnavailable("unavailable")
    )

    snapshot = datadog_incidents.refresh_incident_cache(
        tmp_path / "incidents.json",
        provider=lambda: datadog_incidents.retrieve_active_incidents(
            client=_direct_client(fake_datadog_transport)
        ),
        now=NOW,
    )

    assert snapshot["freshness"] == "unavailable"
    assert snapshot["incidents"] == []
    assert snapshot["count"] is None
    assert snapshot["error"] == "provider-unavailable"


def test_oversized_direct_response_preserves_previous_snapshot(
    tmp_path,
    fake_datadog_transport,
):
    cache_file = tmp_path / "incidents.json"
    previous = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: {"incidents": [_incident()]},
        now=NOW,
    )
    fake_datadog_transport.add_response(
        DatadogResponse(
            200,
            b"{" + b" " * (MAX_RESPONSE_BYTES + 1) + b"}",
            "application/json",
        )
    )

    failed = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: datadog_incidents.retrieve_active_incidents(
            client=_direct_client(fake_datadog_transport)
        ),
        now=NOW + timedelta(seconds=10),
    )

    assert failed["freshness"] == "stale"
    assert failed["error"] == "invalid-response"
    assert failed["incidents"] == previous["incidents"]
    assert failed["lastSuccessfulAt"] == previous["lastSuccessfulAt"]
