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
    assert 'JSON.stringify({ confirmed: true })' in api