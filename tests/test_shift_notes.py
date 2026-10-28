import pytest

from backend.services import shift_notes


SHIFT_DATE = "2099-12-31"


def create_notes_file(
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

    notes_file.write_text(
        f"""# NOC Shift Notes - {SHIFT_DATE}

## Open Tickets
| Ticket | Environment | Summary | Status | Next Step |
|--------|-------------|---------|--------|-----------|

## Active Alerts / Investigations

## Salesforce Tickets

## Escalations

## Changes / Monitor Updates

## Notes for Handover
""",
        encoding="utf-8",
    )

    return notes_file


def test_missing_notes_file(
    noc_root,
):
    result = shift_notes.get_shift_notes(
        SHIFT_DATE
    )

    assert result["exists"] is False
    assert result["sections"] == []
    assert result["activity"] == []


def test_parse_existing_note(
    noc_root,
):
    notes_file = create_notes_file(
        noc_root
    )

    with notes_file.open(
        "a",
        encoding="utf-8",
    ) as file:
        file.write(
            "- 19:30 Test handover note\n"
        )

    result = shift_notes.get_shift_notes(
        SHIFT_DATE
    )

    assert result["exists"] is True

    assert any(
        entry["text"]
        == "Test handover note"
        for entry in result["activity"]
    )


def test_add_note_persists(
    noc_root,
):
    notes_file = create_notes_file(
        noc_root
    )

    result = shift_notes.add_shift_note(
        SHIFT_DATE,
        "Notes for Handover",
        "Persistent test note",
    )

    assert result["saved"] is True

    content = notes_file.read_text(
        encoding="utf-8"
    )

    assert (
        "Persistent test note"
        in content
    )

    reloaded = (
        shift_notes.get_shift_notes(
            SHIFT_DATE
        )
    )

    assert any(
        entry["text"]
        == "Persistent test note"
        for entry in reloaded["activity"]
    )


def test_reject_unknown_section(
    noc_root,
):
    create_notes_file(
        noc_root
    )

    with pytest.raises(
        ValueError
    ):
        shift_notes.add_shift_note(
            SHIFT_DATE,
            "Fake Section",
            "Should not save",
        )


def test_reject_empty_note(
    noc_root,
):
    create_notes_file(
        noc_root
    )

    with pytest.raises(
        ValueError
    ):
        shift_notes.add_shift_note(
            SHIFT_DATE,
            "Notes for Handover",
            "   ",
        )


def test_preserves_other_sections(
    noc_root,
):
    notes_file = create_notes_file(
        noc_root
    )

    original_marker = (
        "| NOC-999 | TEST | Existing | Open | Review |"
    )

    content = notes_file.read_text(
        encoding="utf-8"
    )

    content = content.replace(
        "|--------|-------------|---------|--------|-----------|",
        (
            "|--------|-------------|---------|--------|-----------|\n"
            + original_marker
        ),
    )

    notes_file.write_text(
        content,
        encoding="utf-8",
    )

    shift_notes.add_shift_note(
        SHIFT_DATE,
        "Notes for Handover",
        "New handover note",
    )

    updated = notes_file.read_text(
        encoding="utf-8"
    )

    assert original_marker in updated
    assert "New handover note" in updated


def test_preserves_section_spacing(
    noc_root,
):
    notes_file = create_notes_file(
        noc_root
    )

    shift_notes.add_shift_note(
        SHIFT_DATE,
        "Active Alerts / Investigations",
        "Test alert",
    )

    content = notes_file.read_text(
        encoding="utf-8"
    )

    assert (
        "Test alert\n\n## Salesforce Tickets"
        in content
    )
