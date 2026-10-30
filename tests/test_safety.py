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
    assert "Review and publish local context" in investigation_page
    assert "This does not modify evidence, Datadog, or Jira." in investigation_page
    assert "datadog" not in investigation_service.casefold()
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