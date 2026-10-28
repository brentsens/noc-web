import re
import shutil
import subprocess

from backend.config import NOC_ROOT


SECTION_PATTERN = re.compile(
    r"^##\s+(.+?)\s*$"
)


def get_handover(
    shift_date: str,
) -> dict:

    handover_file = (
        NOC_ROOT
        / shift_date
        / "handover"
        / f"handover-{shift_date}.md"
    )


    if not handover_file.is_file():

        return {
            "shiftDate": shift_date,
            "exists": False,
            "file": None,
            "intro": "",
            "sections": [],
            "closing": "",
            "content": "",
        }


    content = handover_file.read_text(
        encoding="utf-8"
    )


    sections = []
    intro_lines = []
    closing_lines = []

    current_section = None


    for raw_line in content.splitlines():

        line = raw_line.rstrip()


        section_match = (
            SECTION_PATTERN.match(
                line
            )
        )


        if section_match:

            current_section = {
                "name":
                    section_match
                    .group(1)
                    .strip(),

                "content": [],
            }

            sections.append(
                current_section
            )

            continue


        if current_section is None:

            if line.strip():
                intro_lines.append(
                    line
                )

            continue


        current_section[
            "content"
        ].append(line)


    # Pull the email-style closing out of
    # the final section when present.
    if sections:

        final_lines = (
            sections[-1]["content"]
        )

        closing_start = None

        for index, line in enumerate(
            final_lines
        ):

            if line.strip().startswith(
                "Please tag me"
            ):

                closing_start = index
                break


        if closing_start is not None:

            closing_lines = (
                final_lines[
                    closing_start:
                ]
            )

            sections[-1][
                "content"
            ] = final_lines[
                :closing_start
            ]


    normalized_sections = []


    for section in sections:

        section_content = (
            "\n".join(
                section["content"]
            )
            .strip()
        )


        normalized_sections.append({
            "name":
                section["name"],

            "content":
                section_content,
        })


    return {
        "shiftDate":
            shift_date,

        "exists":
            True,

        "file":
            handover_file.name,

        "intro":
            "\n".join(
                intro_lines
            ).strip(),

        "sections":
            normalized_sections,

        "closing":
            "\n".join(
                closing_lines
            ).strip(),

        "content":
            content.strip(),
    }

def generate_handover(
    shift_date: str,
) -> dict:

    handover_file = (
        NOC_ROOT
        / shift_date
        / "handover"
        / f"handover-{shift_date}.md"
    )

    if (
        handover_file.is_file()
        and handover_file.stat().st_size > 0
    ):
        raise FileExistsError(
            f"Handover already exists: {handover_file}"
        )

    command = shutil.which(
        "noc-handover"
    )

    if not command:
        raise FileNotFoundError(
            "noc-handover command not found"
        )

    result = subprocess.run(
        [
            command,
            "--date",
            shift_date,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )

    if result.returncode != 0:

        message = (
            result.stderr.strip()
            or result.stdout.strip()
            or "noc-handover failed"
        )

        raise RuntimeError(
            message
        )

    if (
        not handover_file.is_file()
        or handover_file.stat().st_size == 0
    ):
        raise RuntimeError(
            (
                "noc-handover completed but "
                "the expected handover file "
                "was not created."
            )
        )

    return get_handover(
        shift_date
    )