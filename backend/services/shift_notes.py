import re

from backend.config import NOC_ROOT
from backend.services.tickets import get_operational_work_summary

from datetime import datetime

SECTION_PATTERN = re.compile(
    r"^##\s+(.+?)\s*$"
)

TIME_PATTERN = re.compile(
    r"^-\s+(\d{2}:\d{2})\s+(.+)$"
)


def get_shift_notes(
    shift_date: str,
) -> dict:

    notes_file = (
        NOC_ROOT
        / shift_date
        / "shift-notes.md"
    )


    if not notes_file.is_file():

        return {
            "shiftDate": shift_date,
            "exists": False,
            "sections": [],
            "activity": [],
            "localWork": get_operational_work_summary(),
        }


    content = notes_file.read_text(
        encoding="utf-8"
    )


    sections = []

    current_section = None


    for raw_line in content.splitlines():

        line = raw_line.rstrip()


        section_match = SECTION_PATTERN.match(
                line
            )


        if section_match:

            current_section = {
                "name":
                    section_match.group(1),

                "entries": [],
            }


            sections.append(
                current_section
            )

            continue


        if current_section is None:
            continue


        stripped = line.strip()


        if not stripped:
            continue


        # Ignore the Open Tickets Markdown table.
        if (
            stripped.startswith("|")
        ):
            continue


        if stripped.startswith("- "):

            entry_text = stripped[2:].strip()


            time_match = TIME_PATTERN.match(
                    stripped
                )


            if time_match:

                current_section[
                    "entries"
                ].append({
                    "time":
                        time_match.group(1),

                    "text":
                        time_match.group(2),
                })

            else:

                current_section[
                    "entries"
                ].append({
                    "time": None,
                    "text": entry_text,
                })


        elif stripped.startswith("  - "):

            current_section[
                "entries"
            ].append({
                "time": None,
                "text":
                    stripped[4:].strip(),
            })


    activity = []


    for section in sections:

        for entry in section["entries"]:

            activity.append({
                "section":
                    section["name"],

                "time":
                    entry["time"],

                "text":
                    entry["text"],
            })


    return {
        "shiftDate": shift_date,
        "exists": True,
        "sections": sections,
        "activity": activity,
        "localWork": get_operational_work_summary(),
    }

def add_shift_note(
    shift_date: str,
    category: str,
    text: str,
) -> dict:

    notes_file = (
        NOC_ROOT
        / shift_date
        / "shift-notes.md"
    )

    if not notes_file.is_file():
        raise FileNotFoundError(
            f"Shift notes not found: {notes_file}"
        )

    clean_category = category.strip()

    clean_text = " ".join(
        text.split()
    )

    if not clean_category:
        raise ValueError(
            "Category is required."
        )

    if not clean_text:
        raise ValueError(
            "Note text is required."
        )

    content = notes_file.read_text(
        encoding="utf-8"
    )

    lines = content.splitlines()

    section_heading = (
        f"## {clean_category}"
    )

    try:
        section_index = lines.index(
            section_heading
        )

    except ValueError as error:
        raise ValueError(
            (
                "Shift note category "
                f"not found: {clean_category}"
            )
        ) from error

    insert_index = len(lines)

    for index in range(
        section_index + 1,
        len(lines),
    ):
        if lines[index].startswith(
            "## "
        ):
            insert_index = index
            break

    timestamp = datetime.now().strftime(
        "%H:%M"
    )

    note_line = (
        f"- {timestamp} {clean_text}"
    )

    # Keep a blank line between the final note
    # in a section and the next Markdown heading.
    lines.insert(
        insert_index,
        note_line,
    )

    if (
        insert_index + 1 < len(lines)
        and lines[insert_index + 1].startswith("## ")
    ):
        lines.insert(
            insert_index + 1,
            ""
        )

    updated_content = (
        "\n".join(lines).rstrip()
        + "\n"
    )

    temporary_file = (
        notes_file.with_suffix(
            ".md.tmp"
        )
    )

    temporary_file.write_text(
        updated_content,
        encoding="utf-8",
    )

    temporary_file.replace(
        notes_file
    )

    return {
        "shiftDate": shift_date,
        "category": clean_category,
        "time": timestamp,
        "text": clean_text,
        "saved": True,
        "path": str(notes_file),
    }