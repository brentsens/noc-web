import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.services import investigation_generation
from backend.services.investigation_evidence import build_evidence_package
from backend.services.investigation_preview_store import reset_preview_store_for_tests
from tests.support.investigation_ai import (
    INCIDENT_ID,
    NOTEBOOK_URL,
    SHIFT_DATE,
    evidence_bundle,
    fake_loader,
    fake_runtime,
)


TITLE = "BRINKS Bridge Exceptions – stuck event timestamp parse failure (uspri-prod)"
BRINKS_URL = (
    "https://app.datadoghq.com/notebook/15954893/"
    "brinks-bridge-exceptions-%25E2%2580%2593-stuck-event-timestamp-parse-failure-uspri-prod"
)
BRINKS_IDENTIFIER = (
    "brinks-bridge-exceptions-stuck-event-timestamp-parse-failure-uspri-prod"
)


@pytest.fixture(autouse=True)
def _reset_preview():
    reset_preview_store_for_tests()
    yield
    reset_preview_store_for_tests()


def _prepare(monkeypatch):
    package = build_evidence_package(
        INCIDENT_ID,
        evidence_loader=fake_loader(evidence_bundle()),
    )
    monkeypatch.setattr(
        investigation_generation,
        "build_evidence_package",
        lambda _incident_id, evidence_loader=None: package,
    )
    monkeypatch.setattr(
        investigation_generation,
        "_resolve_provider",
        lambda: fake_runtime(),
    )
    return package


def _preview(
    client,
    *,
    name=TITLE,
    notebook_url=NOTEBOOK_URL,
    incident_id=INCIDENT_ID,
    display_title=None,
):
    body = {
        "incidentId": incident_id,
        "name": name,
        "notebookUrl": notebook_url,
    }
    if display_title is not None:
        body["displayTitle"] = display_title
    return client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/preview",
        json=body,
    )


def test_preview_rejects_invalid_shift_without_generation(
    investigation_workspace, monkeypatch,
):
    _prepare(monkeypatch)

    response = TestClient(app).post(
        "/api/shifts/not-a-date/investigations/preview",
        json={
            "incidentId": INCIDENT_ID,
            "name": TITLE,
            "notebookUrl": NOTEBOOK_URL,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["field"] == "shiftDate"
    assert not list(investigation_workspace.noc_root.glob(".investigation-*"))


def test_preview_rejects_unsafe_names_and_nonapproved_notebook_urls(
    investigation_workspace, monkeypatch,
):
    _prepare(monkeypatch)
    client = TestClient(app)
    for name in ("../escape", "folder/name", r"folder\name", "––", "   ", "safe\nname"):
        response = _preview(client, name=name)
        assert response.status_code == 422
        assert response.json()["detail"]["field"] == "name"
    for url in ("https://example.com/", "http://app.datadoghq.com/notebook/1"):
        response = _preview(client, notebook_url=url)
        assert response.status_code == 422
        assert response.json()["detail"]["field"] == "notebookUrl"


def test_preview_accepts_supported_datadog_notebook_forms(
    investigation_workspace, monkeypatch,
):
    _prepare(monkeypatch)
    client = TestClient(app)
    for url in (
        "https://app.datadoghq.com/notebook/15954893",
        "https://app.datadoghq.com/notebook/15954893/ordinary-slug",
        BRINKS_URL,
    ):
        response = _preview(client, name="BRINKS (uspri-prod)", notebook_url=url)
        assert response.status_code == 200
        assert response.json()["notebookUrl"] == url


def test_preview_normalizes_punctuation_and_repeated_whitespace_in_title(
    investigation_workspace, monkeypatch,
):
    _prepare(monkeypatch)
    display_title = (
        "  BRINKS   Bridge Exceptions – stuck event timestamp parse failure "
        "(uspri-prod)  "
    )

    response = _preview(
        TestClient(app),
        name=display_title,
        notebook_url="https://app.datadoghq.com/notebook/15954893",
    )

    assert response.status_code == 200
    assert response.json()["displayTitle"] == display_title.strip()
    assert response.json()["normalizedName"] == BRINKS_IDENTIFIER


def test_validation_errors_identify_selected_shift_name_incident_and_notebook(
    investigation_workspace, monkeypatch,
):
    _prepare(monkeypatch)
    client = TestClient(app)
    cases = (
        (
            "/api/shifts/not-a-date/investigations/preview",
            {"incidentId": INCIDENT_ID, "name": "Valid title", "notebookUrl": NOTEBOOK_URL},
            "shiftDate",
        ),
        (
            f"/api/shifts/{SHIFT_DATE}/investigations/preview",
            {"incidentId": INCIDENT_ID, "name": "   ", "notebookUrl": NOTEBOOK_URL},
            "name",
        ),
        (
            f"/api/shifts/{SHIFT_DATE}/investigations/preview",
            {"incidentId": INCIDENT_ID, "name": "Valid title", "notebookUrl": "https://example.com/"},
            "notebookUrl",
        ),
        (
            f"/api/shifts/{SHIFT_DATE}/investigations/preview",
            {"incidentId": "", "name": "Valid title", "notebookUrl": NOTEBOOK_URL},
            "incidentId",
        ),
    )
    for path, body, field in cases:
        response = client.post(path, json=body)
        assert response.status_code == 422
        assert response.json()["detail"]["field"] == field


def test_preview_requires_incident_id(investigation_workspace, monkeypatch):
    _prepare(monkeypatch)
    response = TestClient(app).post(
        f"/api/shifts/{SHIFT_DATE}/investigations/preview",
        json={"name": "Valid title", "notebookUrl": NOTEBOOK_URL},
    )

    assert response.status_code == 422
    assert not list(investigation_workspace.noc_root.glob(".investigation-*"))


def test_create_requires_preview_id_and_confirmation(
    investigation_workspace, monkeypatch,
):
    _prepare(monkeypatch)
    client = TestClient(app)
    response = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations",
        json={"name": "Valid title", "notebookUrl": NOTEBOOK_URL, "confirmed": True},
    )
    assert response.status_code == 422

    response = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations",
        json={
            "previewId": "known",
            "name": "Valid title",
            "notebookUrl": NOTEBOOK_URL,
            "confirmed": False,
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "confirmation-required"


def test_preview_and_create_reject_unknown_fields(
    investigation_workspace, monkeypatch,
):
    _prepare(monkeypatch)
    client = TestClient(app)
    response = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/preview",
        json={
            "incidentId": INCIDENT_ID,
            "name": "Valid title",
            "notebookUrl": NOTEBOOK_URL,
            "authorization": "Bearer secret",
        },
    )
    assert response.status_code == 422


LIVE_TITLE = (
    "[PROD] SITEF integration backlog: export service heap exhaustion / "
    "CPU saturation (tenant 6)"
)


def test_slugify_incident_title_is_deterministic_safe_and_bounded():
    from backend.services.investigation_generation import slugify_incident_title

    first = slugify_incident_title(LIVE_TITLE)
    second = slugify_incident_title(LIVE_TITLE)

    assert first == second
    assert first == (
        "prod-sitef-integration-backlog-export-service-heap-exhaustion-"
        "cpu-satur-bedd2675"
    )
    assert len(first) <= 80
    assert first[0].isalnum() and first[-1].isalnum()
    assert all(character.isalnum() or character == "-" for character in first)
    assert not any(character in first for character in "[]:/()")


def test_slugify_incident_title_handles_long_degenerate_and_unsafe_titles():
    from backend.services.investigation_generation import slugify_incident_title

    long_one = slugify_incident_title("A" * 72 + " one")
    long_two = slugify_incident_title("A" * 72 + " two")
    assert long_one != long_two
    assert len(long_one) <= 80
    assert len(long_two) <= 80
    assert slugify_incident_title("") == "datadog-incident"
    assert slugify_incident_title("!!!").startswith("datadog-incident-")
    assert all(
        character.isalnum() or character == "-"
        for character in slugify_incident_title("/// ::: () [x]")
    )
    unicode_slug = slugify_incident_title("é" * 100)
    assert len(unicode_slug.encode("utf-8")) <= 240
    assert len(unicode_slug) <= 80


def test_live_incident_title_preview_uses_safe_local_identifier(
    investigation_workspace, monkeypatch,
):
    _prepare(monkeypatch)
    client = TestClient(app)

    response = _preview(
        client,
        name=None,
        display_title=LIVE_TITLE,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["displayTitle"] == LIVE_TITLE
    assert body["incident"]["id"] == INCIDENT_ID
    assert body["notebookUrl"] == NOTEBOOK_URL
    assert body["normalizedName"] == (
        "prod-sitef-integration-backlog-export-service-heap-exhaustion-"
        "cpu-satur-bedd2675"
    )
    assert len(body["normalizedName"]) <= 80
    assert all(
        character.isalnum() or character == "-"
        for character in body["normalizedName"]
    )

    created = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations",
        json={
            "previewId": body["previewId"],
            "name": body["normalizedName"],
            "notebookUrl": NOTEBOOK_URL,
            "confirmed": True,
        },
    )
    assert created.status_code == 201
    assert created.json()["title"] == LIVE_TITLE
    record = (
        investigation_workspace.noc_root
        / SHIFT_DATE
        / "investigations"
        / body["normalizedName"]
        / "investigation.md"
    )
    content = record.read_text(encoding="utf-8")
    assert f"# Investigation: {LIVE_TITLE}" in content
    assert f"- Investigation Name: {body['normalizedName']}" in content


def test_manual_unsafe_title_still_fails_strict_name_validation(
    investigation_workspace, monkeypatch,
):
    _prepare(monkeypatch)

    response = _preview(
        TestClient(app),
        name=LIVE_TITLE,
        display_title=LIVE_TITLE,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["field"] == "name"
    assert response.json()["detail"]["code"] == "invalid_name"


def test_live_title_collision_is_detected_without_overwrite(
    investigation_workspace, monkeypatch,
):
    _prepare(monkeypatch)
    client = TestClient(app)
    first = _preview(client, name=None, display_title=LIVE_TITLE)
    created = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations",
        json={
            "previewId": first.json()["previewId"],
            "name": first.json()["normalizedName"],
            "notebookUrl": NOTEBOOK_URL,
            "confirmed": True,
        },
    )
    assert created.status_code == 201
    record = (
        investigation_workspace.noc_root
        / SHIFT_DATE
        / "investigations"
        / first.json()["normalizedName"]
        / "investigation.md"
    )
    original = record.read_text(encoding="utf-8")

    second = _preview(client, name=None, display_title=LIVE_TITLE)

    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "investigation-conflict"
    assert record.read_text(encoding="utf-8") == original


def test_explicit_blank_manual_name_is_rejected(
    investigation_workspace, monkeypatch,
):
    _prepare(monkeypatch)

    response = _preview(
        TestClient(app),
        name="",
        display_title=LIVE_TITLE,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["field"] == "name"


def test_live_payload_model_supports_display_title_and_rejects_raw_name(
    investigation_workspace, monkeypatch,
):
    from backend.api.investigations import PreviewInvestigationRequest

    _prepare(monkeypatch)
    body = {
        "incidentId": INCIDENT_ID,
        "displayTitle": LIVE_TITLE,
        "name": LIVE_TITLE,
        "notebookUrl": NOTEBOOK_URL,
    }

    model = PreviewInvestigationRequest.model_validate(body)
    assert model.displayTitle == LIVE_TITLE

    response = TestClient(app).post(
        f"/api/shifts/{SHIFT_DATE}/investigations/preview",
        json=body,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["field"] == "name"
    assert response.json()["detail"]["code"] == "invalid_name"
