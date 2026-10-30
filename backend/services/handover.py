import re
import shutil
import subprocess

from datetime import datetime
from backend.config import NOC_ROOT
from backend.services.tickets import get_operational_work_summary
from backend.services.investigations import get_noc_root, get_reviewed_findings



SECTION_PATTERN = re.compile(
    r"^##\s+(.+?)\s*$"
)

LOCAL_WORK_SECTION_PATTERN = re.compile(
    r"(?ms)^## Active Local NOC Work\s*$.*?(?=^##\s|\Z)"
)
REVIEWED_FINDINGS_SECTION_PATTERN = re.compile(
    r"(?ms)^## Reviewed Investigation Context\s*$.*?(?=^##\s|\Z)"
)


def _validate_local_work(summary: dict) -> None:
    if not summary["available"]:
        raise ValueError(summary["error"])

def _remove_active_local_work_section(handover_file) -> None:
    original = handover_file.read_text(encoding="utf-8")
    content = LOCAL_WORK_SECTION_PATTERN.sub("", original)
    if content != original:
        handover_file.write_text(
            f"{content.rstrip()}\n" if content.strip() else "",
            encoding="utf-8",
        )


def _append_reviewed_findings(handover_file, findings: list[dict]) -> None:
    if not findings:
        return
    lines = ["## Reviewed Investigation Context", ""]
    for finding in findings:
        lines.extend((
            f"- {finding['investigation']}: {finding['finding']}",
            f"  - State: {finding['state']}",
        ))
    content = REVIEWED_FINDINGS_SECTION_PATTERN.sub(
        "", handover_file.read_text(encoding="utf-8")
    ).rstrip()
    handover_file.write_text(
        f"{content}\n\n{chr(10).join(lines)}\n", encoding="utf-8"
    )


def get_handover(
    shift_date: str,
) -> dict:

    noc_root = get_noc_root()
    handover_file = (
        noc_root
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
            "localWork": get_operational_work_summary(),
            "reviewedFindings": get_reviewed_findings(shift_date),
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

        "localWork": get_operational_work_summary(),
        "reviewedFindings": get_reviewed_findings(shift_date),
    }

def generate_handover(
    shift_date: str,
) -> dict:
    local_work = get_operational_work_summary()
    _validate_local_work(local_work)

    noc_root = get_noc_root()
    handover_file = (
        noc_root
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

    _remove_active_local_work_section(handover_file)
    _append_reviewed_findings(handover_file, get_reviewed_findings(shift_date))
    return get_handover(
        shift_date
    )

def regenerate_handover(
    shift_date: str,
) -> dict:
    local_work = get_operational_work_summary()
    _validate_local_work(local_work)

    noc_root = get_noc_root()
    handover_dir = (
        noc_root
        / shift_date
        / "handover"
    )

    handover_file = (
        handover_dir
        / f"handover-{shift_date}.md"
    )

    if (
        not handover_file.is_file()
        or handover_file.stat().st_size == 0
    ):
        raise FileNotFoundError(
            (
                "Existing handover not found: "
                f"{handover_file}"
            )
        )

    command = shutil.which(
        "noc-handover"
    )

    if not command:
        raise FileNotFoundError(
            "noc-handover command not found"
        )

    archive_dir = (
        handover_dir / "archive"
    )

    archive_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d-%H%M%S-%f"
    )

    archive_file = (
        archive_dir
        / (
            f"handover-{shift_date}"
            f"-{timestamp}.md"
        )
    )

    shutil.copy2(
        handover_file,
        archive_file,
    )

    if (
        not archive_file.is_file()
        or archive_file.stat().st_size == 0
    ):
        raise RuntimeError(
            "Handover archive verification failed."
        )

    try:
        result = subprocess.run(
            [
                command,
                "--date",
                shift_date,
                "--force",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )

    except subprocess.TimeoutExpired:

        shutil.copy2(
            archive_file,
            handover_file,
        )

        raise

    if result.returncode != 0:

        # Restore the archived version if
        # regeneration fails.
        shutil.copy2(
            archive_file,
            handover_file,
        )

        message = (
            result.stderr.strip()
            or result.stdout.strip()
            or "Handover regeneration failed"
        )

        raise RuntimeError(
            message
        )

    if (
        not handover_file.is_file()
        or handover_file.stat().st_size == 0
    ):

        shutil.copy2(
            archive_file,
            handover_file,
        )

        raise RuntimeError(
            (
                "Regeneration completed but "
                "the new handover was not created. "
                "The previous handover was restored."
            )
        )

    try:
        _remove_active_local_work_section(handover_file)
        _append_reviewed_findings(handover_file, get_reviewed_findings(shift_date))
    except OSError:
        shutil.copy2(archive_file, handover_file)
        raise

    handover = get_handover(
        shift_date
    )

    handover["regenerated"] = True
    handover["archivedFile"] = str(
        archive_file
    )

    return handover