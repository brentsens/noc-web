import subprocess

from fastapi.testclient import TestClient

from backend.app import app
from backend.services import investigation_generation


SHIFT_DATE = "2099-12-31"
NOTEBOOK_URL = "https://app.datadoghq.com/notebook/123456/example-notebook"
BRINKS_TITLE = "BRINKS Bridge Exceptions – stuck event timestamp parse failure (uspri-prod)"
BRINKS_URL = (
    "https://app.datadoghq.com/notebook/15954893/"
    "brinks-bridge-exceptions-%25E2%2580%2593-stuck-event-timestamp-parse-failure-uspri-prod"
)
BRINKS_IDENTIFIER = (
    "brinks-bridge-exceptions-stuck-event-timestamp-parse-failure-uspri-prod"
)


def _install_noc_inv(
    workspace,
    *,
    exit_code=0,
    contract_version="noc-inv-contract=1",
    write_output=True,
    record_content=None,
):
    executable = workspace.noc_bin / "noc-inv"
    executable.write_text(
        f"""#!/usr/bin/env python3
import json
import pathlib
import sys

args = sys.argv[1:]
record_content = {record_content!r}
if args == ["--contract-version"]:
    print({contract_version!r})
    sys.exit(0)
def value(option):
    return args[args.index(option) + 1]

if record_content is None:
    record_content = (
        f"# Investigation: {{value('--display-title')}}\\n"
        f"- Display Title: {{value('--display-title')}}\\n"
        f"- Investigation Name: {{value('--name')}}\\n"
        f"- Shift Date: {{value('--shift-date')}}\\n"
        f"- FINAL Datadog Notebook: {{value('--notebook-url')}}\\n"
        "- Evidence Provenance: noc-inv\\n"
        "\\n## Summary\\nLatency increased after deployment.\\n"
        "\\n## Confirmed Findings\\nQueue depth is elevated.\\n"
        "\\n## Current Status\\nService remains available.\\n"
        "\\n## Next Actions\\nMonitor queue depth.\\n"
        "\\n## Handover Summary\\nContinue monitoring queue depth.\\n"
    )
output = pathlib.Path(value("--output-dir"))
output.mkdir(parents=True, exist_ok=True)
pathlib.Path(__import__("os").environ["NOC_INV_ARGV_FILE"]).write_text(
    json.dumps(args), encoding="utf-8"
)
print("private subprocess diagnostic")
if {write_output!r}:
    pathlib.Path(output / "investigation.md").write_text(record_content, encoding="utf-8")
sys.exit({exit_code})
""",
        encoding="utf-8",
    )
    executable.chmod(0o700)
    return executable


def _create(
    client,
    *,
    confirmed=True,
    name="Checkout Latency",
    notebook_url=NOTEBOOK_URL,
):
    return client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations",
        json={
            "name": name,
            "notebookUrl": notebook_url,
            "confirmed": confirmed,
        },
    )


def test_create_requires_explicit_confirmation(investigation_workspace, monkeypatch, tmp_path):
    marker = tmp_path / "argv.json"
    monkeypatch.setenv("NOC_INV_ARGV_FILE", str(marker))
    _install_noc_inv(investigation_workspace)

    response = _create(TestClient(app), confirmed=False)

    assert response.status_code == 422
    assert not marker.exists()
    assert not (
        investigation_workspace.noc_root
        / SHIFT_DATE
        / "investigations"
        / "checkout-latency"
    ).exists()


def test_successful_generation_uses_fixed_argv_and_starts_unreviewed(
    investigation_workspace, monkeypatch, tmp_path,
):
    marker = tmp_path / "argv.json"
    monkeypatch.setenv("NOC_INV_ARGV_FILE", str(marker))
    _install_noc_inv(investigation_workspace)
    original_run = subprocess.run
    captured = {}

    def checked_run(args, **kwargs):
        captured.update(kwargs)
        assert isinstance(args, list)
        assert kwargs["shell"] is False
        return original_run(args, **kwargs)

    monkeypatch.setattr(investigation_generation.subprocess, "run", checked_run)
    response = _create(
        TestClient(app),
        name=BRINKS_TITLE,
        notebook_url=BRINKS_URL,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == BRINKS_IDENTIFIER
    assert body["displayTitle"] == BRINKS_TITLE
    assert body["title"] == BRINKS_TITLE
    assert body["generationStatus"] == "completed"
    assert body["validationStatus"] == "ready_for_review"
    assert body["lifecycle"]["reviewState"] == "unreviewed"
    assert body["evidence"]["reference"] == BRINKS_URL
    record = (
        investigation_workspace.noc_root / SHIFT_DATE / "investigations"
        / BRINKS_IDENTIFIER / "investigation.md"
    ).read_text(encoding="utf-8")
    assert f"- Display Title: {BRINKS_TITLE}" in record
    args = __import__("json").loads(marker.read_text(encoding="utf-8"))
    assert args == [
        "--non-interactive",
        "--shift-date", SHIFT_DATE,
        "--name", BRINKS_IDENTIFIER,
        "--display-title", BRINKS_TITLE,
        "--notebook-url", BRINKS_URL,
        "--output-dir", args[-1],
    ]
    assert captured["timeout"] == 3
    assert captured["shell"] is False
    assert "private subprocess diagnostic" not in response.text
    assert not list(investigation_workspace.noc_root.glob(".investigation-generation-*"))


def test_duplicate_normalized_name_conflicts_without_overwrite(
    investigation_workspace, monkeypatch, tmp_path,
):
    monkeypatch.setenv("NOC_INV_ARGV_FILE", str(tmp_path / "argv.json"))
    _install_noc_inv(investigation_workspace)
    client = TestClient(app)

    first = _create(client)
    record = (
        investigation_workspace.noc_root / SHIFT_DATE / "investigations"
        / "checkout-latency" / "investigation.md"
    )
    original = record.read_text(encoding="utf-8")
    second = _create(client)
    preview_collision = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/preview",
        json={
            "name": "Checkout - Latency",
            "notebookUrl": NOTEBOOK_URL,
        },
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"]["field"] == "name"
    assert preview_collision.status_code == 409
    assert preview_collision.json()["detail"]["code"] == "investigation-conflict"
    assert record.read_text(encoding="utf-8") == original


def test_missing_noc_inv_is_controlled_unavailable(investigation_workspace):
    (investigation_workspace.noc_bin / "noc-inv").unlink()

    response = _create(TestClient(app))

    assert response.status_code == 503
    assert "private" not in response.text


def test_incompatible_noc_inv_contract_is_distinguished(
    investigation_workspace, monkeypatch, tmp_path,
):
    marker = tmp_path / "argv.json"
    monkeypatch.setenv("NOC_INV_ARGV_FILE", str(marker))
    _install_noc_inv(investigation_workspace, contract_version="legacy")

    response = _create(TestClient(app))

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "noc-inv-incompatible"
    assert not marker.exists()


def test_missing_copilot_cli_is_controlled_unavailable(investigation_workspace):
    _install_noc_inv(investigation_workspace)
    (investigation_workspace.noc_bin / "copilot").unlink()

    response = _create(TestClient(app))

    assert response.status_code == 503
    assert "private" not in response.text


def test_storage_permission_failure_is_controlled_and_does_not_run_noc_inv(
    investigation_workspace, monkeypatch,
):
    executable = _install_noc_inv(investigation_workspace)

    def denied(*args, **kwargs):
        raise PermissionError("private path")

    monkeypatch.setattr(investigation_generation.tempfile, "TemporaryDirectory", denied)
    response = _create(TestClient(app))

    assert response.status_code == 503
    assert "private path" not in response.text
    assert executable.is_file()


def test_timeout_is_bounded_and_diagnostics_are_sanitized(
    investigation_workspace, monkeypatch,
):
    executable = _install_noc_inv(investigation_workspace)
    captured = {}

    def timed_out(args, **kwargs):
        if args[-1] == "--contract-version":
            return subprocess.CompletedProcess(args, 0, stdout="noc-inv-contract=1\n")
        captured.update(kwargs)
        assert args[0] == str(executable)
        raise subprocess.TimeoutExpired(args, kwargs["timeout"], stderr="secret token")

    monkeypatch.setattr(investigation_generation.subprocess, "run", timed_out)
    response = _create(TestClient(app))

    assert response.status_code == 504
    assert captured["shell"] is False
    assert captured["timeout"] == 3
    assert "secret token" not in response.text
    assert "stderr" not in response.text
    assert not list(investigation_workspace.noc_root.glob(".investigation-generation-*"))


def test_nonzero_exit_and_missing_output_are_controlled_failures(
    investigation_workspace, monkeypatch, tmp_path,
):
    monkeypatch.setenv("NOC_INV_ARGV_FILE", str(tmp_path / "argv.json"))
    _install_noc_inv(investigation_workspace, exit_code=6)

    response = _create(TestClient(app))

    assert response.status_code == 503
    assert "private subprocess diagnostic" not in response.text
    assert response.json()["detail"]["code"] == "datadog-mcp-unavailable"


def test_successful_command_without_generated_file_is_not_reported_as_created(
    investigation_workspace, monkeypatch, tmp_path,
):
    monkeypatch.setenv("NOC_INV_ARGV_FILE", str(tmp_path / "argv.json"))
    _install_noc_inv(investigation_workspace, write_output=False)

    response = _create(TestClient(app))

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "generated-output-missing"
    assert not (
        investigation_workspace.noc_root / SHIFT_DATE / "investigations"
        / "checkout-latency"
    ).exists()


def test_path_traversal_is_rejected_before_command_execution(
    investigation_workspace, monkeypatch, tmp_path,
):
    marker = tmp_path / "argv.json"
    monkeypatch.setenv("NOC_INV_ARGV_FILE", str(marker))
    _install_noc_inv(investigation_workspace)

    response = TestClient(app).post(
        f"/api/shifts/{SHIFT_DATE}/investigations",
        json={
            "name": "../outside",
            "notebookUrl": NOTEBOOK_URL,
            "confirmed": True,
        },
    )

    assert response.status_code == 422
    assert not marker.exists()


def test_creation_is_isolated_to_the_selected_shift(
    investigation_workspace, monkeypatch, tmp_path,
):
    monkeypatch.setenv("NOC_INV_ARGV_FILE", str(tmp_path / "argv.json"))
    _install_noc_inv(investigation_workspace)
    client = TestClient(app)

    created = _create(client)
    other_shift = client.get("/api/shifts/2099-12-30/investigations")

    assert created.status_code == 201
    assert other_shift.status_code == 200
    assert other_shift.json()["investigations"] == []


def test_malformed_record_is_retained_and_withheld_from_review_and_propagation(
    investigation_workspace, monkeypatch, tmp_path,
):
    monkeypatch.setenv("NOC_INV_ARGV_FILE", str(tmp_path / "argv.json"))
    malformed = (
        "# Investigation: Checkout Latency\n"
        "- Investigation Name: checkout-latency\n"
        "- Shift Date: 2099-12-30\n"
        f"- FINAL Datadog Notebook: {NOTEBOOK_URL}\n"
        "- Evidence Provenance: noc-inv\n"
        "\n## Summary\nTBD\n"
        "\n## Confirmed Findings\nNone\n"
        "\n## Current Status\nService remains available.\n"
        "\n## Next Actions\nMonitor.\n"
        "\n## Handover Summary\nNo handover summary.\n"
    )
    _install_noc_inv(investigation_workspace, record_content=malformed)
    client = TestClient(app)

    created = _create(client)
    record_path = (
        investigation_workspace.noc_root / SHIFT_DATE / "investigations"
        / "checkout-latency" / "investigation.md"
    )

    assert created.status_code == 201
    assert created.json()["validationStatus"] == "needs_review"
    assert record_path.read_text(encoding="utf-8") == (
        investigation_generation._include_display_title(malformed, "Checkout Latency")
    )
    assert "TBD" in created.json()["advisory"]["content"]
    reviewed = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/checkout-latency/review",
        json={"confirmed": True, "finding": "Queue high", "state": "monitoring"},
    )
    assert reviewed.status_code == 422
    assert not (record_path.parent / "reviewed-context.json").exists()
    assert investigation_generation.investigations.get_reviewed_findings(SHIFT_DATE) == []

    rejected = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/checkout-latency/reject",
        json={"confirmed": True},
    )
    assert rejected.status_code == 200
    assert rejected.json()["lifecycle"]["reviewState"] == "rejected"


def test_noc_inv_malformed_output_status_is_retained_for_review(
    investigation_workspace, monkeypatch, tmp_path,
):
    monkeypatch.setenv("NOC_INV_ARGV_FILE", str(tmp_path / "argv.json"))
    _install_noc_inv(investigation_workspace, exit_code=8)

    response = _create(TestClient(app))

    assert response.status_code == 201
    assert response.json()["generationStatus"] == "completed"
    assert response.json()["validationStatus"] == "needs_review"
    assert response.json()["lifecycle"]["reviewState"] == "unreviewed"
    assert "noc_inv_validation" in response.json()["validationIssues"]
