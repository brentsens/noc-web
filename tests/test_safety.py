def test_noc_root_is_temporary(
    noc_root,
):

    assert noc_root.exists()

    assert str(noc_root).startswith(
        "/tmp/"
    )

    assert str(noc_root) != (
        "/home/bsmith/noc"
    )


def test_workflow_pages_use_shared_url_context_without_mutating_helpers():
    from pathlib import Path

    frontend = Path(__file__).parents[1] / "frontend"
    pages = (
        "start-shift.html",
        "index.html",
        "tickets.html",
        "investigations.html",
        "status.html",
        "end-shift.html",
    )

    for page in pages:
        content = (frontend / page).read_text(encoding="utf-8")
        assert "./js/workflow-context.js" in content
        assert "initializeWorkflow" in content

    context = (frontend / "js" / "workflow-context.js").read_text(
        encoding="utf-8"
    )
    assert "?shift=" in context
    assert "method: \"POST\"" not in context
    assert "method: \"PATCH\"" not in context


def test_visible_workflow_mutations_are_confirmation_gated():
    from pathlib import Path

    frontend = Path(__file__).parents[1] / "frontend"

    for page in ("start-shift.html", "tickets.html", "end-shift.html"):
        assert "window.confirm" in (
            frontend / page
        ).read_text(encoding="utf-8")

    api = (frontend / "js" / "api.js").read_text(encoding="utf-8")
    assert "confirmed = false" in api
    assert "body: JSON.stringify({ confirmed })" in api


def test_investigations_use_only_reviewed_context_and_no_direct_datadog():
    from pathlib import Path

    frontend = Path(__file__).parents[1] / "frontend"
    investigation_page = (frontend / "investigations.html").read_text(
        encoding="utf-8"
    )
    investigation_service = (
        Path(__file__).parents[1] / "backend" / "services" / "investigations.py"
    ).read_text(encoding="utf-8")

    assert "AI analysis is advisory" in investigation_page
    assert "Operator-reviewed finding" in investigation_page
    assert "Lifecycle" in investigation_page
    assert "This does not modify evidence, Datadog, or Jira." in investigation_page
    assert "get_incident_snapshot(schedule_refresh=False)" in investigation_service
    assert "get_reviewed_findings" in investigation_service


def test_assistant_has_no_direct_datadog_or_operational_tools():
    from pathlib import Path

    root = Path(__file__).parents[1] / "backend" / "services"
    assistant_service = (root / "assistant.py").read_text(encoding="utf-8").casefold()
    context = (root / "assistant_context.py").read_text(encoding="utf-8").casefold()
    adapter = (root / "copilot_mcp.py").read_text(encoding="utf-8").casefold()

    assert "datadog" not in context
    assert "subprocess" not in assistant_service
    assert "subprocess" not in adapter

def test_provider_configuration_absence_does_not_block_non_assistant_workflows(
    noc_root,
    monkeypatch,
):
    from fastapi.testclient import TestClient

    from backend.app import app, configure_assistant_provider

    shift = "2026-10-29"
    monkeypatch.delenv("NOC_WEB_AI_PROVIDER", raising=False)
    configure_assistant_provider(None, None)
    client = TestClient(app)

    for path in (
        "/api/health",
        "/api/tickets",
        f"/api/status/{shift}",
        f"/api/shifts/{shift}/notes",
        f"/api/shifts/{shift}/handover",
        f"/api/shifts/{shift}/investigations",
    ):
        assert client.get(path).status_code == 200

    assistant = client.post(f"/api/shifts/{shift}/assistant/questions", json={
        "shiftDate": shift,
        "question": "What requires attention?",
        "providerDisclosureAcknowledged": True,
    })
    assert assistant.status_code == 503
    assert assistant.json()["detail"]["code"] == "assistant-provider-not-configured"
