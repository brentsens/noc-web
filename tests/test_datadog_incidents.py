import json
import multiprocessing
import subprocess
from datetime import datetime, timedelta, timezone
import threading
import time

import pytest

from backend.services import datadog_incidents


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


def _cli_event(event_type, data):
    return json.dumps({"type": event_type, "data": data})


def _cli_jsonl_response(
    content,
    *,
    include_tool_request=True,
    include_tool_start=True,
    include_tool_completion=True,
    request_server="datadog",
    request_tool="search_datadog_incidents",
    start_server="datadog",
    start_tool="search_datadog_incidents",
    tool_success=True,
    completion_call_id="incident-search-call",
):
    call_id = "incident-search-call"
    requests = (
        [
            {
                "toolCallId": call_id,
                "mcpServerName": request_server,
                "mcpToolName": request_tool,
            }
        ]
        if include_tool_request
        else []
    )
    events = [
        _cli_event(
            "assistant.message",
            {"content": "Searching current incidents.", "toolRequests": requests},
        )
    ]
    if include_tool_start:
        events.append(
            _cli_event(
                "tool.execution_start",
                {
                    "toolCallId": call_id,
                    "mcpServerName": start_server,
                    "mcpToolName": start_tool,
                    "toolName": f"{start_server}-{start_tool}",
                },
            )
        )
    if include_tool_completion:
        events.append(
            _cli_event(
                "tool.execution_complete",
                {
                    "toolCallId": completion_call_id,
                    "success": tool_success,
                },
            )
        )
    events.extend(
        (
            _cli_event("assistant.message", {"content": content}),
            json.dumps({"type": "result", "exitCode": 0}),
        )
    )
    return "\n".join(events)


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


@pytest.mark.parametrize(
    ("failure", "expected_error"),
    [
        ("missing", "copilot-unavailable"),
        ("timeout", "timeout"),
    ],
)
def test_cli_unavailable_and_timeout_keep_first_snapshot_unavailable(
    tmp_path,
    monkeypatch,
    failure,
    expected_error,
):
    cache_file = tmp_path / "incidents.json"
    monkeypatch.setattr(
        datadog_incidents.shutil,
        "which",
        lambda name: None if failure == "missing" else "/usr/bin/copilot",
    )
    if failure == "timeout":
        monkeypatch.setattr(
            datadog_incidents.subprocess,
            "run",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                subprocess.TimeoutExpired(args[0], kwargs["timeout"])
            ),
        )

    snapshot = datadog_incidents.refresh_incident_cache(cache_file, now=NOW)

    assert snapshot["freshness"] == "unavailable"
    assert snapshot["incidents"] == []
    assert snapshot["lastSuccessfulAt"] is None
    assert snapshot["error"] == expected_error


@pytest.mark.parametrize(
    ("stdout", "returncode", "expected_error", "expected_rule"),
    [
        ("PRIVATE_PROVIDER_OUTPUT", 0, "invalid-response", "invalid_json"),
        (
            'Here is the JSON: {"incidents":[]} PRIVATE_PROVIDER_OUTPUT',
            0,
            "invalid-response",
            "invalid_json",
        ),
        (
            '```json\n{"incidents":[]}\n```',
            0,
            "invalid-response",
            "invalid_json",
        ),
        (
            '{"incidents":[]} Additional commentary PRIVATE_PROVIDER_OUTPUT',
            0,
            "invalid-response",
            "invalid_json",
        ),
        (
            '{"incidents":[]} {"incidents":[]}',
            0,
            "invalid-response",
            "invalid_json",
        ),
        ("[]", 0, "invalid-response", "invalid_envelope_type"),
        ("private response", 1, "provider-unavailable", None),
    ],
)
def test_cli_malformed_and_downstream_failures_are_redacted(
    tmp_path,
    monkeypatch,
    caplog,
    stdout,
    returncode,
    expected_error,
    expected_rule,
):
    monkeypatch.setattr(
        datadog_incidents.shutil,
        "which",
        lambda name: "/usr/bin/copilot",
    )
    monkeypatch.setattr(
        datadog_incidents.subprocess,
        "run",
        lambda arguments, **options: subprocess.CompletedProcess(
            arguments,
            returncode,
            _cli_jsonl_response(stdout) if returncode == 0 else stdout,
            "private stderr with credential",
        ),
    )

    cache_file = tmp_path / "incidents.json"
    previous = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: {"incidents": [_incident()]},
        now=NOW,
    )
    snapshot = datadog_incidents.refresh_incident_cache(
        cache_file,
        now=NOW + timedelta(seconds=10),
    )

    assert snapshot["freshness"] == "stale"
    assert snapshot["error"] == expected_error
    assert snapshot["incidents"] == previous["incidents"]
    assert snapshot["lastSuccessfulAt"] == previous["lastSuccessfulAt"]
    assert "private" not in caplog.text
    assert "PRIVATE_PROVIDER_OUTPUT" not in caplog.text
    assert "credential" not in caplog.text
    diagnostics = [
        record.getMessage()
        for record in caplog.records
        if record.name == datadog_incidents.__name__
    ]
    if expected_rule is None:
        assert diagnostics == ["Datadog incident refresh failed: code=provider-unavailable"]
    else:
        assert diagnostics == [
            "Datadog incident refresh failed: code=invalid-response "
            f"provider=github-copilot-cli rule={expected_rule} "
            "category=envelope providerStatus=invalid"
        ]


def test_invalid_cli_event_stream_preserves_previous_snapshot_and_is_redacted(
    tmp_path,
    monkeypatch,
    caplog,
):
    cache_file = tmp_path / "incidents.json"
    previous = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: {"incidents": [_incident()]},
        now=NOW,
    )
    monkeypatch.setattr(
        datadog_incidents.shutil,
        "which",
        lambda name: "/usr/bin/copilot",
    )
    monkeypatch.setattr(
        datadog_incidents.subprocess,
        "run",
        lambda arguments, **options: subprocess.CompletedProcess(
            arguments,
            0,
            "PRIVATE_CLI_OUTPUT",
            "private stderr with credential",
        ),
    )

    failed = datadog_incidents.refresh_incident_cache(
        cache_file,
        now=NOW + timedelta(seconds=10),
    )

    assert failed["freshness"] == "stale"
    assert failed["error"] == "invalid-response"
    assert failed["incidents"] == previous["incidents"]
    assert failed["lastSuccessfulAt"] == previous["lastSuccessfulAt"]
    assert "PRIVATE_CLI_OUTPUT" not in caplog.text
    assert "private" not in caplog.text
    assert "credential" not in caplog.text
    assert (
        "provider=github-copilot-cli rule=invalid_cli_event_stream "
        "category=envelope providerStatus=invalid"
    ) in caplog.text


@pytest.mark.parametrize(
    "event_options",
    [
        {"include_tool_request": False},
        {"include_tool_start": False},
        {"include_tool_completion": False},
        {"tool_success": False},
        {"request_server": "another-server"},
        {"request_tool": "get_datadog_incident"},
        {"start_server": "another-server"},
        {"completion_call_id": "unmatched-call"},
    ],
    ids=[
        "no-request",
        "no-start",
        "no-completion",
        "failed-completion",
        "wrong-server",
        "wrong-tool",
        "wrong-start-server",
        "unmatched-completion",
    ],
)
def test_cli_rejects_valid_json_without_successful_incident_search(
    tmp_path,
    monkeypatch,
    caplog,
    event_options,
):
    cache_file = tmp_path / "incidents.json"
    previous = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: {"incidents": [_incident()]},
        now=NOW,
    )
    monkeypatch.setattr(
        datadog_incidents.shutil,
        "which",
        lambda name: "/usr/bin/copilot",
    )
    monkeypatch.setattr(
        datadog_incidents.subprocess,
        "run",
        lambda arguments, **options: subprocess.CompletedProcess(
            arguments,
            0,
            _cli_jsonl_response(
                json.dumps({"incidents": [_incident("fabricated")]}),
                **event_options,
            ),
            "",
        ),
    )

    failed = datadog_incidents.refresh_incident_cache(
        cache_file,
        now=NOW + timedelta(seconds=10),
    )

    assert failed["freshness"] == "stale"
    assert failed["error"] == "invalid-response"
    assert failed["incidents"] == previous["incidents"]
    assert failed["lastSuccessfulAt"] == previous["lastSuccessfulAt"]
    assert (
        "provider=github-copilot-cli rule=incident_search_not_verified "
        "category=envelope providerStatus=invalid"
    ) in caplog.text


def test_copilot_invocation_is_read_only_scoped_and_uses_shell_false(monkeypatch):
    monkeypatch.setattr(
        datadog_incidents.shutil,
        "which",
        lambda command: "/usr/bin/copilot" if command == "copilot" else None,
    )
    monkeypatch.setenv("COPILOT_ALLOW_ALL", "true")
    monkeypatch.setenv("GH_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("DATADOG_API_KEY", "test-key")
    calls = []

    def run(arguments, **options):
        calls.append((arguments, options))
        return subprocess.CompletedProcess(
            arguments,
            0,
            "\n".join(
                (
                    _cli_event("assistant.message", {"content": "Tool commentary."}),
                    _cli_jsonl_response(
                        json.dumps({"incidents": [_incident()]})
                    ),
                )
            ),
            "",
        )

    monkeypatch.setattr(datadog_incidents.subprocess, "run", run)

    result = datadog_incidents.retrieve_active_incidents()

    assert result == {"incidents": [_incident()]}
    assert len(calls) == 1
    arguments, options = calls[0]
    assert arguments[:4] == [
        "/usr/bin/copilot",
        "--trust-folder",
        "--available-tools",
        datadog_incidents.DATADOG_MCP_SERVER,
    ]
    assert (
        f"--allow-tool={datadog_incidents.DATADOG_INCIDENT_TOOL}"
        in arguments
    )
    assert options["shell"] is False
    assert not {
        "COPILOT_ALLOW_ALL",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "DATADOG_API_KEY",
    } & options["env"].keys()
    assert options["timeout"] == datadog_incidents.COPILOT_TIMEOUT_SECONDS
    assert "--allow-all" not in arguments
    assert "--allow-all-tools" not in arguments
    assert "--yolo" not in arguments
    assert arguments.count(
        f"--allow-tool={datadog_incidents.DATADOG_INCIDENT_TOOL}"
    ) == 1
    assert "state_category:live" in arguments[-1]
    assert "read-only" in arguments[-1].casefold()
    assert "consumed directly by a strict JSON parser" in arguments[-1]
    assert "call the exact tool datadog(search_datadog_incidents)" in arguments[-1]
    assert "Return exactly one valid JSON object and nothing else" in arguments[-1]
    assert "Do not use Markdown code fences" in arguments[-1]
    assert "introductory or trailing prose, tool commentary, citations outside" in arguments[-1]
    assert "Never add Datadog, MCP, or provider fields" in arguments[-1]
    assert "The only permitted item keys are" in arguments[-1]
    assert '"id": required non-empty string' in arguments[-1]
    assert (
        'Current states may be represented as "active"/"stable" or "ACTIVE"/"STABLE"'
        in arguments[-1]
    )
    assert "without changing its casing or wording" in arguments[-1]
    assert 'Exclude "resolved"/"RESOLVED" incidents' in arguments[-1]
    assert "at most 100 incidents" in arguments[-1]
    assert "every incident ID must be unique" in arguments[-1]
    assert '"createdAt"' in arguments[-1]
    assert '"startedAt"' not in arguments[-1]
    assert arguments[arguments.index("--output-format") + 1] == "json"
    assert arguments[arguments.index("--stream") + 1] == "off"
