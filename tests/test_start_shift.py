from backend.services import start_shift


SHIFT_DATE = "2099-12-31"


def test_preflight_missing_workspace(
    noc_root,
    monkeypatch,
):
    monkeypatch.setattr(
        start_shift.shutil,
        "which",
        lambda command: f"/mock/{command}",
    )

    result = (
        start_shift.get_start_shift_preflight(
            SHIFT_DATE
        )
    )

    assert result["ready"] is True
    assert result["started"] is False

    assert result["execution"]["enabled"] is True

    assert len(
        result["plannedActions"]
    ) > 0


def test_start_creates_workspace(
    noc_root,
):
    result = start_shift.start_shift(
        SHIFT_DATE
    )

    shift_dir = (
        noc_root / SHIFT_DATE
    )

    assert result["started"] is True

    assert shift_dir.is_dir()

    assert (
        shift_dir / "investigations"
    ).is_dir()

    assert (
        shift_dir / "reports"
    ).is_dir()

    assert (
        shift_dir / "handover"
    ).is_dir()

    assert (
        shift_dir / "shift-notes.md"
    ).is_file()


def test_start_preserves_existing_notes(
    noc_root,
):
    shift_dir = (
        noc_root / SHIFT_DATE
    )

    shift_dir.mkdir(
        parents=True
    )

    notes_file = (
        shift_dir / "shift-notes.md"
    )

    original = (
        "# Existing notes\n"
        "- Do not overwrite me\n"
    )

    notes_file.write_text(
        original,
        encoding="utf-8",
    )

    start_shift.start_shift(
        SHIFT_DATE
    )

    assert notes_file.read_text(
        encoding="utf-8"
    ) == original


def test_start_updates_today_link(
    noc_root,
):
    start_shift.start_shift(
        SHIFT_DATE
    )

    today_link = (
        noc_root / "today"
    )

    assert today_link.is_symlink()

    assert today_link.resolve() == (
        noc_root / SHIFT_DATE
    ).resolve()


def test_started_state_detected(
    noc_root,
    monkeypatch,
):
    monkeypatch.setattr(
        start_shift.shutil,
        "which",
        lambda command: f"/mock/{command}",
    )

    start_shift.start_shift(
        SHIFT_DATE
    )

    result = (
        start_shift.get_start_shift_preflight(
            SHIFT_DATE
        )
    )

    assert result["ready"] is True
    assert result["started"] is True

    assert (
        result["plannedActions"]
        == []
    )

    assert (
        result["execution"]["enabled"]
        is False
    )

def test_start_refreshes_jira_queue(
    noc_root,
    monkeypatch,
):
    monkeypatch.setattr(
        start_shift,
        "refresh_jira_ticket_queue",
        lambda: {
            "count": 28,
            "tickets": [],
        },
    )

    result = start_shift.start_shift(
        SHIFT_DATE
    )

    assert result["started"] is True

    assert result["jiraQueue"] == {
        "success": True,
        "count": 28,
        "warning": None,
    }


def test_jira_failure_does_not_block_start(
    noc_root,
    monkeypatch,
):
    def fail_jira():
        raise RuntimeError(
            "Jira unavailable"
        )

    monkeypatch.setattr(
        start_shift,
        "refresh_jira_ticket_queue",
        fail_jira,
    )

    result = start_shift.start_shift(
        SHIFT_DATE
    )

    assert result["started"] is True

    assert result["jiraQueue"] == {
        "success": False,
        "count": 0,
        "warning": "Jira unavailable",
    }

    shift_dir = (
        noc_root / SHIFT_DATE
    )

    assert shift_dir.is_dir()

    assert (
        shift_dir / "shift-notes.md"
    ).is_file()