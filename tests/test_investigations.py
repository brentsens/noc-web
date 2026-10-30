from fastapi.testclient import TestClient

from backend.app import app
from backend.services import dashboard, handover, investigations, shift_notes, status


SHIFT_DATE = "2099-12-31"


def _investigation(noc_root, source="noc-inv"):
    directory = noc_root / SHIFT_DATE / "investigations" / "memory"
    directory.mkdir(parents=True)
    (directory / "investigation.md").write_text(
        f"""# Investigation: Memory pressure
- Status: active
- Source of truth: {source}
- Datadog Notebook: https://example.test/notebook/123

## Summary
raw Datadog log body must never become an API field
""",
        encoding="utf-8",
    )
    if source == "noc-inv":
        (directory / "noc-inv.log").write_text(
            "raw secret-like source output", encoding="utf-8"
        )
    return directory


def test_investigation_projection_is_read_only_and_excludes_raw_evidence(noc_root):
    _investigation(noc_root)

    result = investigations.get_investigation(SHIFT_DATE, "memory")

    assert result["evidence"] == {
        "provenance": "noc-inv",
        "availability": "available",
        "access": "read-only",
        "reference": "https://example.test/notebook/123",
    }
    assert result["advisory"]["available"] is True
    assert "summary" not in result
    assert "raw Datadog" not in str(result)


def test_review_requires_confirmation_and_only_publishes_concise_context(noc_root):
    directory = _investigation(noc_root)
    client = TestClient(app)

    response = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/memory/review",
        json={"confirmed": False, "finding": "Memory is high", "state": "monitoring"},
    )

    assert response.status_code == 422
    assert not (directory / "reviewed-context.json").exists()

    response = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/memory/review",
        json={"confirmed": True, "finding": "Memory is high", "state": "monitoring"},
    )

    assert response.status_code == 200
    assert response.json()["reviewedFinding"]["finding"] == "Memory is high"
    assert investigations.get_reviewed_findings(SHIFT_DATE) == [{
        "investigation": "memory",
        "finding": "Memory is high",
        "state": "monitoring",
        "reviewedAt": response.json()["reviewedFinding"]["reviewedAt"],
        "reviewedBy": "operator",
    }]


def test_non_noc_inv_or_copilot_source_cannot_be_reviewed(noc_root):
    _investigation(noc_root, source="Jira ticket")

    try:
        investigations.review_investigation(
            SHIFT_DATE, "memory", "Should not publish", "blocked"
        )
    except ValueError as error:
        assert "noc-inv or Copilot MCP" in str(error)
    else:
        raise AssertionError("Unsupported evidence provenance was accepted")


def test_rejected_advisory_is_not_propagated(noc_root):
    _investigation(noc_root)
    client = TestClient(app)

    response = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/memory/reject",
        json={"confirmed": True},
    )

    assert response.status_code == 200
    assert response.json()["lifecycle"]["reviewState"] == "rejected"
    assert investigations.get_reviewed_findings(SHIFT_DATE) == []


def test_generated_needs_review_cannot_be_reviewed_but_can_be_explicitly_rejected(
    noc_root,
):
    directory = noc_root / SHIFT_DATE / "investigations" / "generated"
    directory.mkdir(parents=True)
    (directory / "investigation.md").write_text(
        "# Investigation: Generated record\n"
        "- Status: active\n"
        "- Source of truth: noc-inv\n"
        "- Evidence Provenance: noc-inv\n"
        "- FINAL Datadog Notebook: https://app.datadoghq.com/notebook/123/example\n"
        "\n## Summary\nTBD\n",
        encoding="utf-8",
    )
    (directory / "generation-status.json").write_text(
        '{"generationStatus":"completed","validationStatus":"needs_review",'
        '"shiftDate":"2099-12-31","name":"generated",'
        '"notebookUrl":"https://app.datadoghq.com/notebook/123/example",'
        '"provenance":"noc-inv"}',
        encoding="utf-8",
    )
    client = TestClient(app)

    review = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/generated/review",
        json={"confirmed": True, "finding": "Queue high", "state": "monitoring"},
    )
    assert review.status_code == 422
    assert not (directory / "reviewed-context.json").exists()
    assert investigations.get_reviewed_findings(SHIFT_DATE) == []

    rejected = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/generated/reject",
        json={"confirmed": True},
    )
    assert rejected.status_code == 200
    assert rejected.json()["lifecycle"]["reviewState"] == "rejected"


def test_corrupt_investigations_return_unavailable_projections_without_changing_files(noc_root):
    _investigation(noc_root)
    corrupt_context = noc_root / SHIFT_DATE / "investigations" / "corrupt-context"
    corrupt_context.mkdir()
    (corrupt_context / "investigation.md").write_text(
        "# Investigation: Context validation\n- Status: active\n",
        encoding="utf-8",
    )
    context_file = corrupt_context / "reviewed-context.json"
    context_file.write_text("{not json", encoding="utf-8")
    corrupt_investigation = noc_root / SHIFT_DATE / "investigations" / "corrupt-investigation"
    corrupt_investigation.mkdir()
    (corrupt_investigation / "investigation.md").write_text(
        "- Status: active\n", encoding="utf-8"
    )

    results = {result["name"]: result for result in investigations.get_investigations(SHIFT_DATE)}

    assert results["memory"]["evidence"]["availability"] == "available"
    assert results["corrupt-context"]["lifecycle"]["reviewState"] == "unavailable"
    assert results["corrupt-context"]["error"]["code"] == "reviewed-context-unavailable"
    assert results["corrupt-context"]["reviewedFinding"] is None
    assert results["corrupt-context"]["advisory"]["available"] is False
    assert results["corrupt-investigation"]["evidence"]["availability"] == "unavailable"
    assert results["corrupt-investigation"]["error"]["code"] == "investigation-unavailable"
    assert context_file.read_text(encoding="utf-8") == "{not json"

    detail = investigations.get_investigation(SHIFT_DATE, "corrupt-investigation")
    assert detail["error"]["code"] == "investigation-unavailable"


def test_only_reviewed_context_reaches_operational_projections(noc_root, monkeypatch):
    _investigation(noc_root)
    monkeypatch.setattr(dashboard, "get_jira_ticket_queue", lambda: {"tickets": []})
    monkeypatch.setattr(status, "get_jira_ticket_queue", lambda: {"tickets": []})

    pending = [
        dashboard.get_dashboard(SHIFT_DATE),
        status.get_status(SHIFT_DATE),
        shift_notes.get_shift_notes(SHIFT_DATE),
        handover.get_handover(SHIFT_DATE),
    ]
    assert all(result["reviewedFindings"] == [] for result in pending)
    assert all("raw secret-like source output" not in str(result) for result in pending)

    investigations.review_investigation(
        SHIFT_DATE, "memory", "Memory remains elevated", "monitoring"
    )
    dashboard_result = dashboard.get_dashboard(SHIFT_DATE)
    status_result = status.get_status(SHIFT_DATE)
    notes_result = shift_notes.get_shift_notes(SHIFT_DATE)

    for result in (dashboard_result, status_result, notes_result):
        assert result["reviewedFindings"][0]["finding"] == "Memory remains elevated"
        assert "raw secret-like source output" not in str(result)
