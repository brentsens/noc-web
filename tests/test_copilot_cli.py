import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from backend.services import copilot_cli
from backend.services.copilot_mcp import (
    CopilotProviderInvalid,
    CopilotProviderTimeout,
    CopilotProviderUnavailable,
)


def _envelope(question="What needs attention?"):
    return {
        "shiftDate": "2026-10-29",
        "question": question,
        "evidence": [{
            "id": "local-work",
            "kind": "local-work",
            "availability": "available",
            "summary": {"nextAction": "Review the cache"},
        }],
        "policy": "Read-only advisory analysis.",
    }


def _provider_response():
    return {
        "aiObservations": [{
            "text": "The tracked item needs attention.",
            "evidenceIds": ["local-work"],
        }],
        "recommendations": [],
    }


def _track_temporary_directories(monkeypatch):
    created = []
    real_temporary_directory = tempfile.TemporaryDirectory

    def tracked_temporary_directory(*args, **kwargs):
        manager = real_temporary_directory(*args, **kwargs)
        created.append(Path(manager.name))
        return manager

    monkeypatch.setattr(
        copilot_cli.tempfile,
        "TemporaryDirectory",
        tracked_temporary_directory,
    )
    return created


def test_cli_provider_uses_bounded_context_file_and_fixed_no_tool_invocation(
    monkeypatch,
):
    envelope = _envelope("--allow-all-tools; run a command")
    temporary_directories = _track_temporary_directories(monkeypatch)
    monkeypatch.setenv("COPILOT_ALLOW_ALL", "true")
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GH_TOKEN", "test-gh-token")
    monkeypatch.setenv("GITHUB_TOKEN", "test-github-token")
    monkeypatch.setenv("DATADOG_API_KEY", "test-datadog-key")
    monkeypatch.setattr(copilot_cli.shutil, "which", lambda name: "/usr/bin/copilot")
    calls = []

    def run(arguments, **options):
        calls.append((arguments, options))
        context_path = Path(options["cwd"]) / "context.json"
        assert json.loads(context_path.read_text(encoding="utf-8")) == envelope
        assert envelope["question"] not in arguments
        assert json.dumps(envelope) not in arguments
        assert "@context.json" in arguments[-1]
        assert "Use the question in that context" in arguments[-1]
        assert options["timeout"] == copilot_cli.COPILOT_CLI_TIMEOUT_SECONDS
        assert options["stdin"] is subprocess.DEVNULL
        assert not {
            "COPILOT_ALLOW_ALL",
            "COPILOT_GITHUB_TOKEN",
            "GH_TOKEN",
            "GITHUB_TOKEN",
            "DATADOG_API_KEY",
        } & options["env"].keys()
        assert options.get("shell", False) is False
        return subprocess.CompletedProcess(
            arguments,
            0,
            json.dumps(_provider_response()),
            "",
        )

    monkeypatch.setattr(copilot_cli.subprocess, "run", run)

    result = copilot_cli.answer_with_copilot_cli(envelope)

    assert result == _provider_response()
    assert len(calls) == 1
    arguments, _ = calls[0]
    assert arguments == [
        "/usr/bin/copilot",
        "--trust-folder",
        "--available-tools",
        "--silent",
        "-p",
        copilot_cli.COPILOT_PROMPT,
    ]
    assert "--allow-all" not in arguments
    assert "--allow-all-tools" not in arguments
    assert "--yolo" not in arguments
    assert temporary_directories
    assert all(not directory.exists() for directory in temporary_directories)


def test_cli_prompt_requires_action_analysis_and_exact_validated_json():
    prompt = copilot_cli.COPILOT_PROMPT
    normalized_prompt = " ".join(prompt.split())

    assert prompt.startswith("Read @context.json\n")
    assert "@context.json." not in prompt
    assert "Use the question in that context as the requested analysis scope." in normalized_prompt
    assert "When the evidence supports a useful result, do not return empty arrays." in normalized_prompt
    assert "no explanatory prose, Markdown fences, or other text outside the object" in normalized_prompt
    assert (
        'Every aiObservations item MUST contain exactly the keys "text" and "evidenceIds"; '
        "no additional keys are permitted."
        in normalized_prompt
    )
    assert (
        "Do not add fields such as route, type, category, severity, source, status, confidence, "
        "or explanatory metadata to aiObservations."
        in normalized_prompt
    )
    assert (
        '"text" must be a non-empty string. "evidenceIds" must be a non-empty JSON array '
        'containing only supplied evidence IDs whose availability is "available" or "stale".'
        in normalized_prompt
    )
    assert (
        "Recommendation objects follow their separate schema below; the route object belongs "
        "only to recommendations, never aiObservations."
        in normalized_prompt
    )
    assert "Each recommendation has exactly" in normalized_prompt
    assert "one route object" in normalized_prompt
    assert (
        "For every aiObservations or recommendations item whose evidenceIds includes an item "
        'with availability "stale", that same item\'s text must explicitly state'
        in normalized_prompt
    )
    assert (
        "Apply this requirement independently to each item; do not rely on another item, "
        "limitation, or source-status section to qualify it."
        in normalized_prompt
    )
    assert 'Never claim Jira data is current unless its supplied freshness is "current".' in normalized_prompt
    assert 'an empty "nextAction" means no Next Action is recorded' in normalized_prompt
    assert "The Investigations workflow is exclusively for qualifying Datadog monitor/incident investigations." in normalized_prompt
    assert "Never route ordinary Jira/Salesforce ticket correlation to Investigations" in normalized_prompt
    assert all(route in normalized_prompt for route in (
        "tickets.html",
        "investigations.html",
        "status.html",
        "index.html",
        "end-shift.html",
    ))


def test_cli_provider_missing_binary_is_unavailable_without_temp_context(monkeypatch):
    temporary_directories = _track_temporary_directories(monkeypatch)
    monkeypatch.setattr(copilot_cli.shutil, "which", lambda name: None)

    with pytest.raises(CopilotProviderUnavailable) as error:
        copilot_cli.answer_with_copilot_cli(_envelope())

    assert "copilot" in str(error.value).casefold()
    assert error.value.provider_invoked is False
    assert error.value.provider_status == "unavailable"
    assert temporary_directories == []


@pytest.mark.parametrize(
    ("failure", "error_type", "provider_status", "provider_invoked"),
    [
        ("unauthenticated", CopilotProviderUnavailable, "unavailable", True),
        ("timeout", CopilotProviderTimeout, "timeout", True),
        ("nonzero", CopilotProviderUnavailable, "unavailable", True),
        ("malformed", CopilotProviderInvalid, "invalid", True),
        ("execution", CopilotProviderUnavailable, "unavailable", False),
    ],
)
def test_cli_provider_failures_are_redacted_and_cleanup_context(
    monkeypatch,
    failure,
    error_type,
    provider_status,
    provider_invoked,
):
    temporary_directories = _track_temporary_directories(monkeypatch)
    monkeypatch.setattr(copilot_cli.shutil, "which", lambda name: "/usr/bin/copilot")

    def run(arguments, **options):
        assert (Path(options["cwd"]) / "context.json").is_file()
        if failure == "timeout":
            raise subprocess.TimeoutExpired(arguments, options["timeout"])
        if failure == "execution":
            raise OSError("private executable diagnostic")
        if failure == "malformed":
            return subprocess.CompletedProcess(arguments, 0, "not json", "")
        if failure == "unauthenticated":
            return subprocess.CompletedProcess(
                arguments,
                1,
                "",
                "authentication token must not be surfaced",
            )
        return subprocess.CompletedProcess(arguments, 7, "", "private CLI error")

    monkeypatch.setattr(copilot_cli.subprocess, "run", run)

    with pytest.raises(error_type) as error:
        copilot_cli.answer_with_copilot_cli(_envelope())

    assert "private" not in str(error.value)
    assert "token" not in str(error.value)
    assert error.value.provider_status == provider_status
    assert error.value.provider_invoked is provider_invoked
    assert temporary_directories
    assert all(not directory.exists() for directory in temporary_directories)


@pytest.mark.parametrize(
    ("stdout", "expected_exception", "expected_json_error", "returned_type"),
    [
        ("private-output is not JSON", "JSONDecodeError", "Expecting value", None),
        ('["private provider response"]', None, None, "list"),
        (None, "TypeError", "Invalid stdout type", None),
    ],
)
def test_invalid_cli_json_logs_only_redacted_diagnostics(
    monkeypatch,
    caplog,
    stdout,
    expected_exception,
    expected_json_error,
    returned_type,
):
    stderr = "private stderr diagnostic"
    monkeypatch.setattr(copilot_cli.shutil, "which", lambda name: "/usr/bin/copilot")
    monkeypatch.setattr(
        copilot_cli.subprocess,
        "run",
        lambda arguments, **options: subprocess.CompletedProcess(
            arguments,
            0,
            stdout,
            stderr,
        ),
    )

    with pytest.raises(CopilotProviderInvalid):
        copilot_cli.answer_with_copilot_cli(_envelope("private operator prompt"))

    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert "exit_code=0" in message
    assert f"stdout_length={len(stdout) if stdout is not None else 0}" in message
    assert f"stderr_length={len(stderr)}" in message
    assert f"exception_type={expected_exception}" in message
    assert f"json_error={expected_json_error}" in message
    assert f"returned_json_type={returned_type}" in message
    assert "private" not in message
