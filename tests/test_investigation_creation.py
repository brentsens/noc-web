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


def test_preview_is_read_only_and_returns_exact_confirmation_values(
    investigation_workspace, monkeypatch,
):
    root = investigation_workspace.noc_root
    before = sorted(path.relative_to(root) for path in root.rglob("*"))
    monkeypatch.setattr(
        investigation_generation.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Preview must not start a subprocess.")
        ),
    )

    response = TestClient(app).post(
        f"/api/shifts/{SHIFT_DATE}/investigations/preview",
        json={"name": BRINKS_TITLE, "notebookUrl": BRINKS_URL},
    )

    assert response.status_code == 200
    assert response.json() == {
        "shiftDate": SHIFT_DATE,
        "displayTitle": BRINKS_TITLE,
        "normalizedName": BRINKS_IDENTIFIER,
        "notebookUrl": BRINKS_URL,
        "target": f"{SHIFT_DATE}/{BRINKS_IDENTIFIER}",
        "generation": "noc-inv -> GitHub Copilot CLI -> Datadog MCP",
        "datadogReadOnly": True,
        "requiresOperatorReview": True,
    }
    assert sorted(path.relative_to(root) for path in root.rglob("*")) == before


def test_preview_rejects_invalid_shift_without_generation(investigation_workspace):
    response = TestClient(app).post(
        "/api/shifts/not-a-date/investigations/preview",
        json={
            "name": "Checkout Latency",
            "notebookUrl": NOTEBOOK_URL,
        },
    )

    assert response.status_code == 422
    assert not list(investigation_workspace.noc_root.glob(".investigation-*"))


def test_preview_rejects_unsafe_names_and_nonapproved_notebook_urls(
    investigation_workspace,
):
    client = TestClient(app)
    for name in (
        "../escape",
        "folder/name",
        r"folder\name",
        "––",
        "   ",
        "safe\nname",
    ):
        response = client.post(
            f"/api/shifts/{SHIFT_DATE}/investigations/preview",
            json={"name": name, "notebookUrl": NOTEBOOK_URL},
        )
        assert response.status_code == 422
        assert response.json()["detail"]["field"] == "name"

    for url in (
        "http://app.datadoghq.com/notebook/123456/example",
        "file://app.datadoghq.com/notebook/123456/example",
        "javascript://app.datadoghq.com/notebook/123456/example",
        "data:text/plain,notebook",
        "ftp://app.datadoghq.com/notebook/123456/example",
        "https://evil.example/notebook/123456/example",
        "https://app.datadoghq.com.evil.example/notebook/123456/example",
        "https://app.datadoghq.com/notebook/not-numeric/example",
        "https://app.datadoghq.com/notebook/123456/%2e%2e",
        "https://app.datadoghq.com/notebook/123456/bad%2",
        "https://app.datadoghq.com/notebook/123456/example?shift=2099-12-31",
    ):
        response = client.post(
            f"/api/shifts/{SHIFT_DATE}/investigations/preview",
            json={"name": "Checkout Latency", "notebookUrl": url},
        )
        assert response.status_code == 422
        assert response.json()["detail"]["field"] == "notebookUrl"


def test_preview_accepts_supported_datadog_notebook_forms(investigation_workspace):
    client = TestClient(app)
    for url in (
        "https://app.datadoghq.com/notebook/15954893",
        "https://app.datadoghq.com/notebook/15954893/ordinary-slug",
        BRINKS_URL,
    ):
        response = client.post(
            f"/api/shifts/{SHIFT_DATE}/investigations/preview",
            json={"name": "BRINKS (uspri-prod)", "notebookUrl": url},
        )
        assert response.status_code == 200
        assert response.json()["notebookUrl"] == url


def test_preview_normalizes_punctuation_and_repeated_whitespace_in_title(
    investigation_workspace,
):
    display_title = "  BRINKS   Bridge Exceptions – stuck event timestamp parse failure (uspri-prod)  "
    response = TestClient(app).post(
        f"/api/shifts/{SHIFT_DATE}/investigations/preview",
        json={
            "name": display_title,
            "notebookUrl": "https://app.datadoghq.com/notebook/15954893",
        },
    )

    assert response.status_code == 200
    assert response.json()["displayTitle"] == display_title.strip()
    assert response.json()["normalizedName"] == BRINKS_IDENTIFIER


def test_validation_errors_identify_selected_shift_name_and_notebook_fields(
    investigation_workspace,
):
    client = TestClient(app)
    cases = (
        (
            "/api/shifts/not-a-date/investigations/preview",
            {"name": "Valid title", "notebookUrl": NOTEBOOK_URL},
            "shiftDate",
        ),
        (
            f"/api/shifts/{SHIFT_DATE}/investigations/preview",
            {"name": "   ", "notebookUrl": NOTEBOOK_URL},
            "name",
        ),
        (
            f"/api/shifts/{SHIFT_DATE}/investigations/preview",
            {"name": "Valid title", "notebookUrl": "https://example.com/"},
            "notebookUrl",
        ),
        (
            f"/api/shifts/{SHIFT_DATE}/investigations/preview",
            {"notebookUrl": NOTEBOOK_URL},
            "name",
        ),
        (
            f"/api/shifts/{SHIFT_DATE}/investigations/preview",
            {"name": "Valid title"},
            "notebookUrl",
        ),
    )
    for path, body, field in cases:
        response = client.post(path, json=body)
        assert response.status_code == 422
        assert response.json()["detail"]["field"] == field
