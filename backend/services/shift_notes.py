import re

from backend.config import NOC_ROOT


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
    }