import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.services import investigation_generation
from backend.services.copilot_mcp import (
    ProviderInvalid,
    ProviderTimeout,
    ProviderUnavailable,
)
from backend.services.investigation_evidence import build_evidence_package
from backend.services.investigation_preview_store import (
    InvestigationPreviewStore,
    reset_preview_store_for_tests,
)
from tests.support.investigation_ai import (
    INCIDENT_ID,
    NOTEBOOK_ID,
    NOTEBOOK_URL,
    SHIFT_DATE,
    Clock,
    evidence_bundle,
    fake_loader,
    fake_runtime,
    valid_output,
)


TITLE = "Checkout Latency"
NORMALIZED = "checkout-latency"


@pytest.fixture(autouse=True)
def _reset_preview():
    reset_preview_store_for_tests()
    yield
    reset_preview_store_for_tests()


def _package(bundle=None):
    return build_evidence_package(
        INCIDENT_ID,
        evidence_loader=fake_loader(bundle or evidence_bundle()),
    )


def _prepare(monkeypatch, *, bundle=None, runtime=None, packages=None):
    if packages is None:
        packages = [_package(bundle)]
    iterator = iter(packages)

    def load(_incident_id, evidence_loader=None):
        try:
            return next(iterator)
        except StopIteration:
            return packages[-1]

    monkeypatch.setattr(investigation_generation, "build_evidence_package", load)
    runtime = runtime or fake_runtime()
    monkeypatch.setattr(
        investigation_generation,
        "_resolve_provider",
        lambda: runtime,
    )
    return packages[0], runtime


def _preview(client, *, name=TITLE, notebook_url=NOTEBOOK_URL, incident_id=INCIDENT_ID):
    return client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/preview",
        json={
            "incidentId": incident_id,
            "name": name,
            "notebookUrl": notebook_url,
        },
    )


def _create(
    client,
    preview_id,
    *,
    name=TITLE,
    notebook_url=NOTEBOOK_URL,
    confirmed=True,
):
    return client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations",
        json={
            "previewId": preview_id,
            "name": name,
            "notebookUrl": notebook_url,
            "confirmed": confirmed,
        },
    )


def _record_dir(workspace):
    return (
        workspace.noc_root
        / SHIFT_DATE
        / "investigations"
        / NORMALIZED
    )


def test_preview_is_non_generative_and_returns_evidence_summary(
    investigation_workspace, monkeypatch,
):
    package, runtime = _prepare(monkeypatch)
    before = sorted(
        path.relative_to(investigation_workspace.noc_root)
        for path in investigation_workspace.noc_root.rglob("*")
    )

    response = _preview(TestClient(app))

    assert response.status_code == 200
    body = response.json()
    assert body["previewId"]
    assert body["shiftDate"] == SHIFT_DATE
    assert body["displayTitle"] == TITLE
    assert body["normalizedName"] == NORMALIZED
    assert body["notebookUrl"] == NOTEBOOK_URL
    assert body["incident"]["id"] == INCIDENT_ID
    assert body["evidence"]["status"] == "complete"
    assert body["evidence"]["incidentId"] == f"incident:{INCIDENT_ID}"
    assert body["evidence"]["notebookCount"] == 1
    assert body["evidence"]["monitorCount"] == 1
    assert body["provider"]["configuredProvider"] == "deepseek-api"
    assert body["provider"]["model"] == "deepseek-flash"
    assert body["datadogReadOnly"] is True
    assert body["requiresOperatorReview"] is True
    assert "Checkout runbook. See monitor" not in response.text
    assert runtime.calls == []
    assert sorted(
        path.relative_to(investigation_workspace.noc_root)
        for path in investigation_workspace.noc_root.rglob("*")
    ) == before


def test_confirmed_generation_persists_ai_evidence_record(
    investigation_workspace, monkeypatch,
):
    package, runtime = _prepare(monkeypatch)
    client = TestClient(app)
    preview = _preview(client)
    assert preview.status_code == 200

    response = _create(client, preview.json()["previewId"])

    assert response.status_code == 201
    body = response.json()
    assert body["generationStatus"] == "completed"
    assert body["validationStatus"] == "ready_for_review"
    assert body["lifecycleStatus"] == "ready_for_review"
    assert body["evidence"]["provenance"] == "ai-evidence"
    assert body["evidence"]["status"] == "complete"
    assert body["evidence"]["references"]
    assert body["datadogIncidentReference"] is None
    directory = _record_dir(investigation_workspace)
    assert (directory / "investigation.md").is_file()
    assert (directory / "generation-status.json").is_file()
    assert (directory / "evidence-provenance.json").is_file()
    assert (directory / "reviewed-context.json").is_file()
    content = (directory / "investigation.md").read_text(encoding="utf-8")
    assert "- Evidence Provenance: ai-evidence" in content
    assert "- Evidence Status: COMPLETE" in content
    assert "## Confirmed Findings" in content
    assert f"notebook:{NOTEBOOK_ID}" in content
    status = json.loads(
        (directory / "generation-status.json").read_text(encoding="utf-8")
    )
    assert status["provider"] == "deepseek-api"
    assert status["model"] == "deepseek-flash"
    assert status["provenance"] == "ai-evidence"
    provenance = json.loads(
        (directory / "evidence-provenance.json").read_text(encoding="utf-8")
    )
    assert provenance["packageDigest"] == package["digest"]
    assert provenance["availability"] == "complete"
    assert len(runtime.calls) == 1


def test_generation_works_without_noc_inv_or_copilot(
    investigation_workspace, monkeypatch,
):
    (investigation_workspace.noc_bin / "noc-inv").unlink(missing_ok=True)
    (investigation_workspace.noc_bin / "copilot").unlink(missing_ok=True)
    _prepare(monkeypatch)
    client = TestClient(app)

    preview = _preview(client)
    response = _create(client, preview.json()["previewId"])

    assert preview.status_code == 200
    assert response.status_code == 201


def test_create_requires_explicit_confirmation(investigation_workspace, monkeypatch):
    _, runtime = _prepare(monkeypatch)
    client = TestClient(app)
    preview = _preview(client)

    response = _create(client, preview.json()["previewId"], confirmed=False)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "confirmation-required"
    assert runtime.calls == []
    assert not _record_dir(investigation_workspace).exists()


def test_create_requires_an_active_preview(investigation_workspace, monkeypatch):
    _, runtime = _prepare(monkeypatch)
    client = TestClient(app)

    missing = _create(client, "unknown-preview")

    assert missing.status_code == 409
    assert missing.json()["detail"]["code"] == "preview-required"
    assert runtime.calls == []
    assert not _record_dir(investigation_workspace).exists()


def test_preview_is_single_use(investigation_workspace, monkeypatch):
    _, runtime = _prepare(monkeypatch)
    client = TestClient(app)
    preview = _preview(client)
    preview_id = preview.json()["previewId"]

    first = _create(client, preview_id)
    second = _create(client, preview_id)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"]["code"] in {
        "preview-used",
        "preview-required",
        "investigation-conflict",
    }
    assert len(runtime.calls) == 1


def test_preview_request_mismatch_fails_closed(investigation_workspace, monkeypatch):
    _, runtime = _prepare(monkeypatch)
    client = TestClient(app)
    preview = _preview(client)
    preview_id = preview.json()["previewId"]

    response = _create(
        client,
        preview_id,
        name="Different Investigation",
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "preview-mismatch"
    assert runtime.calls == []
    assert not (investigation_workspace.noc_root / SHIFT_DATE / "investigations" / "different-investigation").exists()


def test_preview_expiry_fails_closed(investigation_workspace, monkeypatch):
    clock = Clock()
    store = InvestigationPreviewStore(clock=clock)
    monkeypatch.setattr(
        investigation_generation,
        "get_preview_store",
        lambda: store,
    )
    _prepare(monkeypatch)
    client = TestClient(app)
    preview = _preview(client)
    clock.advance(11 * 60)

    response = _create(client, preview.json()["previewId"])

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "preview-expired"


def test_preview_stale_when_evidence_changes(investigation_workspace, monkeypatch):
    package_one = _package(evidence_bundle())
    package_two = _package(
        evidence_bundle(
            monitor_query="avg(last_5m):sum:checkout.errors{*}.as_count() > 50",
        )
    )
    _, runtime = _prepare(
        monkeypatch,
        packages=[package_one, package_two],
    )
    client = TestClient(app)
    preview = _preview(client)

    response = _create(client, preview.json()["previewId"])

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "preview-stale"
    assert runtime.calls == []
    assert not _record_dir(investigation_workspace).exists()


def test_partial_evidence_is_system_disclosed(investigation_workspace, monkeypatch):
    bundle = evidence_bundle(unavailable_monitor=True)
    _prepare(monkeypatch, bundle=bundle)
    client = TestClient(app)
    preview = _preview(client)
    assert preview.json()["evidence"]["status"] == "partial"
    assert preview.json()["evidence"]["unavailable"]

    response = _create(client, preview.json()["previewId"])

    assert response.status_code == 201
    body = response.json()
    assert body["evidence"]["status"] == "partial"
    content = (_record_dir(investigation_workspace) / "investigation.md").read_text(
        encoding="utf-8"
    )
    assert "- Evidence Status: PARTIAL" in content
    assert "## Evidence Availability" in content
    assert "Partial evidence:" in content


def test_partial_evidence_contradiction_is_rejected(
    investigation_workspace, monkeypatch,
):
    bundle = evidence_bundle(unavailable_monitor=True)
    package = _package(bundle)
    output = valid_output(package)
    output["summary"] = [
        f"All evidence is complete and current ({package['incident']['id']})."
    ]
    runtime = fake_runtime(output=output)
    _prepare(monkeypatch, bundle=bundle, runtime=runtime)
    client = TestClient(app)
    preview = _preview(client)

    response = _create(client, preview.json()["previewId"])

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "ai-output-invalid"
    assert not _record_dir(investigation_workspace).exists()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda output: output.pop("confirmedFindings"),
        lambda output: output.__setitem__(
            "summary",
            ["Unsupported evidence (monitor:999999)."],
        ),
        lambda output: output.__setitem__("summary", ["No citation here."]),
        lambda output: output.__setitem__("summary", ["TBD"]),
        lambda output: output.__setitem__(
            "summary",
            ["Authorization: Bearer secret-token-value incident:bad"],
        ),
    ],
)
def test_invalid_ai_output_fails_closed(
    investigation_workspace, monkeypatch, mutate,
):
    package = _package()
    output = valid_output(package)
    mutate(output)
    runtime = fake_runtime(output=output)
    _prepare(monkeypatch, runtime=runtime)
    client = TestClient(app)
    preview = _preview(client)

    response = _create(client, preview.json()["previewId"])

    assert response.status_code == 422
    assert response.json()["detail"]["code"] in {
        "ai-output-invalid",
        "evidence-reference-invalid",
    }
    assert not _record_dir(investigation_workspace).exists()


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (ProviderTimeout("timeout"), 504, "provider-timeout"),
        (ProviderUnavailable("down"), 503, "provider-unavailable"),
        (ProviderInvalid("bad"), 502, "provider-invalid-response"),
    ],
)
def test_provider_failures_fail_closed_without_fallback(
    investigation_workspace, monkeypatch, error, status_code, code,
):
    runtime = fake_runtime(error=error)
    _prepare(monkeypatch, runtime=runtime)
    client = TestClient(app)
    preview = _preview(client)

    response = _create(client, preview.json()["previewId"])

    assert response.status_code == status_code
    assert response.json()["detail"]["code"] == code
    assert len(runtime.calls) == 1
    assert not _record_dir(investigation_workspace).exists()


def test_provider_not_ready_fails_closed(
    investigation_workspace, monkeypatch,
):
    runtime = fake_runtime(readiness="notConfigured")
    _prepare(monkeypatch, runtime=runtime)

    response = _preview(TestClient(app))

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "provider-not-configured"


def test_non_current_incident_fails_closed(investigation_workspace, monkeypatch):
    monkeypatch.setattr(
        investigation_generation,
        "build_evidence_package",
        lambda _incident_id, evidence_loader=None: build_evidence_package(
            _incident_id,
            evidence_loader=fake_loader(evidence_bundle(state="RESOLVED")),
        ),
    )
    monkeypatch.setattr(
        investigation_generation,
        "_resolve_provider",
        lambda: fake_runtime(),
    )

    response = _preview(TestClient(app))

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "incident-not-current"


def test_selected_shift_and_collision_protection(
    investigation_workspace, monkeypatch,
):
    _prepare(monkeypatch)
    client = TestClient(app)
    preview = _preview(client)
    created = _create(client, preview.json()["previewId"])
    assert created.status_code == 201
    record = _record_dir(investigation_workspace) / "investigation.md"
    original = record.read_text(encoding="utf-8")

    second_preview = _preview(client)
    assert second_preview.status_code == 409
    assert second_preview.json()["detail"]["code"] == "investigation-conflict"
    assert record.read_text(encoding="utf-8") == original

    other_shift = client.get("/api/shifts/2099-12-30/investigations")
    assert other_shift.status_code == 200


def test_credentials_are_not_exposed_to_provider_or_outputs(
    investigation_workspace, monkeypatch, caplog,
):
    caplog.set_level("DEBUG")
    sentinel = "SENTINEL-DO-NOT-EXPOSE"
    monkeypatch.setenv("NOC_WEB_DEEPSEEK_API_KEY", sentinel)
    monkeypatch.setenv("DEEPSEEK_API_KEY", sentinel)
    monkeypatch.setenv("DD_ACCESS_TOKEN", sentinel)
    monkeypatch.setenv("NOC_WEB_DATADOG_ACCESS_TOKEN", sentinel)
    _, runtime = _prepare(monkeypatch)
    client = TestClient(app)

    preview = _preview(client)
    created = _create(client, preview.json()["previewId"])

    assert preview.status_code == 200
    assert created.status_code == 201
    assert sentinel not in preview.text
    assert sentinel not in created.text
    assert sentinel not in caplog.text
    assert sentinel not in json.dumps(runtime.calls)
    for path in _record_dir(investigation_workspace).iterdir():
        if path.is_file():
            assert sentinel not in path.read_text(encoding="utf-8")


def test_provider_change_invalidates_preview(investigation_workspace, monkeypatch):
    package = _package()
    monkeypatch.setattr(
        investigation_generation,
        "build_evidence_package",
        lambda _incident_id, evidence_loader=None: package,
    )
    runtimes = [fake_runtime(model="deepseek-flash")]
    monkeypatch.setattr(
        investigation_generation,
        "_resolve_provider",
        lambda: runtimes[0],
    )
    client = TestClient(app)
    preview = _preview(client)
    runtimes[0] = fake_runtime(model="deepseek-chat")

    response = _create(client, preview.json()["previewId"])

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "preview-stale"
    assert runtimes[0].calls == []
    assert not _record_dir(investigation_workspace).exists()


def test_preview_shift_mismatch_fails_closed(investigation_workspace, monkeypatch):
    _, runtime = _prepare(monkeypatch)
    client = TestClient(app)
    preview = _preview(client)

    response = client.post(
        "/api/shifts/2099-12-30/investigations",
        json={
            "previewId": preview.json()["previewId"],
            "name": TITLE,
            "notebookUrl": NOTEBOOK_URL,
            "confirmed": True,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "preview-mismatch"
    assert runtime.calls == []


@pytest.mark.parametrize(
    ("code", "status_code"),
    [
        ("evidence-timeout", 504),
        ("evidence-unavailable", 503),
        ("evidence-invalid", 422),
        ("evidence-too-large", 422),
        ("evidence-credential-detected", 422),
    ],
)
def test_evidence_failures_map_to_sanitized_errors(
    investigation_workspace, monkeypatch, code, status_code,
):
    from backend.services.investigation_evidence import InvestigationEvidenceError

    def fail(_incident_id, evidence_loader=None):
        raise InvestigationEvidenceError(code, "Controlled evidence failure.")

    monkeypatch.setattr(investigation_generation, "build_evidence_package", fail)
    monkeypatch.setattr(
        investigation_generation,
        "_resolve_provider",
        lambda: fake_runtime(),
    )

    response = _preview(TestClient(app))

    assert response.status_code == status_code
    assert response.json()["detail"]["code"] == code
    assert "Controlled evidence failure" in response.text


def test_live_deepseek_unsupplied_citation_fails_closed(
    investigation_workspace, monkeypatch,
):
    package = _package()
    output = valid_output(package)
    output["confirmedFindings"] = [
        "Checkout error monitor is alerting (monitor:999999)."
    ]
    runtime = fake_runtime(output=output)
    _prepare(monkeypatch, runtime=runtime)
    client = TestClient(app)
    preview = _preview(client)

    response = _create(client, preview.json()["previewId"])

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "evidence-reference-invalid"
    assert len(runtime.calls) == 1
    assert not _record_dir(investigation_workspace).exists()
