import html
import re
from pathlib import Path

from backend.config import NOC_ROOT


TITLE_PATTERN = re.compile(
    r"^# Investigation:\s*(.+?)\s*$",
    re.MULTILINE,
)

SECTION_PATTERN = re.compile(
    r"^##\s+(.+?)\s*$"
)

METADATA_PATTERN = re.compile(
    r"^-\s+([^:]+):\s*(.*)$"
)

HREF_PATTERN = re.compile(
    r'href="([^"]+)"'
)

URL_PATTERN = re.compile(
    r"https://[^\s<>\"']+"
)


SECTION_KEYS = {
    "Summary": "summary",
    "Service / Environment": "serviceEnvironment",
    "Customer / Service Impact": "customerImpact",
    "Timeline": "timeline",
    "Confirmed Findings": "confirmedFindings",
    "Current Status": "currentStatus",
    "Actions Taken": "actionsTaken",
    "Escalation / Ownership": "escalationOwnership",
    "Next Actions": "nextActions",
    "Handover Summary": "handoverSummary",
}


def clean_inline_html(value: str) -> str:
    value = html.unescape(value)

    href_match = HREF_PATTERN.search(value)

    if href_match:
        return html.unescape(
            href_match.group(1)
        )

    return value.strip()


def extract_notebook_url(
    investigation_dir: Path,
    metadata: dict,
) -> str:

    notebook_file = (
        investigation_dir
        / "notebook-url.txt"
    )

    if notebook_file.is_file():

        try:
            content = notebook_file.read_text(
                encoding="utf-8"
            ).strip()

            href_match = HREF_PATTERN.search(
                content
            )

            if href_match:
                return html.unescape(
                    href_match.group(1)
                )

            url_match = URL_PATTERN.search(
                html.unescape(content)
            )

            if url_match:
                return url_match.group(0)

        except OSError:
            pass


    metadata_value = metadata.get(
        "Datadog Notebook",
        "",
    )

    if metadata_value:
        return clean_inline_html(
            metadata_value
        )

    return ""


def parse_investigation(
    investigation_file: Path,
) -> dict:

    raw_content = investigation_file.read_text(
        encoding="utf-8"
    )

    title_match = TITLE_PATTERN.search(
        raw_content
    )

    if not title_match:
        raise ValueError(
            "Investigation title not found"
        )


    # Ignore noc-inv and Copilot execution output
    # before the real investigation heading.
    content = raw_content[
        title_match.start():
    ]


    title = title_match.group(1).strip()

    metadata = {}

    sections = {}

    current_section = None

    preamble_complete = False


    for raw_line in content.splitlines():

        line = raw_line.rstrip()


        if line.startswith(
            "# Investigation:"
        ):
            continue


        section_match = SECTION_PATTERN.match(
            line
        )

        if section_match:

            preamble_complete = True

            current_section = (
                section_match
                .group(1)
                .strip()
            )

            sections[current_section] = []

            continue


        if not preamble_complete:

            metadata_match = (
                METADATA_PATTERN.match(
                    line
                )
            )

            if metadata_match:

                key = (
                    metadata_match
                    .group(1)
                    .strip()
                )

                value = (
                    metadata_match
                    .group(2)
                    .strip()
                )

                metadata[key] = value

            continue


        if current_section is not None:

            sections[
                current_section
            ].append(line)


    normalized_sections = {}

    for heading, lines in sections.items():

        value = "\n".join(
            lines
        ).strip()

        normalized_sections[
            SECTION_KEYS.get(
                heading,
                heading,
            )
        ] = value


    investigation_dir = (
        investigation_file.parent
    )


    supporting_files = {
        "investigation": True,

        "notebookUrl": (
            investigation_dir
            .joinpath(
                "notebook-url.txt"
            )
            .is_file()
        ),

        "copilotSummary": (
            investigation_dir
            .joinpath(
                "evidence",
                "copilot-notebook-summary.md",
            )
            .is_file()
        ),

        "log": (
            investigation_dir
            .joinpath(
                "noc-inv.log"
            )
            .is_file()
        ),
    }


    result = {
        "name":
            investigation_dir.name,

        "title":
            title,

        "status":
            metadata.get(
                "Status",
                "",
            ),

        "source":
            metadata.get(
                "Source of truth",
                "",
            ),

        "captureMethod":
            metadata.get(
                "Capture method",
                "",
            ),

        "notebookUrl":
            extract_notebook_url(
                investigation_dir,
                metadata,
            ),

        "supportingFiles":
            supporting_files,
    }


    for api_key in SECTION_KEYS.values():

        result[api_key] = (
            normalized_sections.get(
                api_key,
                "",
            )
        )


    return result


def get_investigations(
    shift_date: str,
) -> list:

    investigation_root = (
        NOC_ROOT
        / shift_date
        / "investigations"
    )


    if not investigation_root.is_dir():
        return []


    investigations = []


    for investigation_file in sorted(
        investigation_root.glob(
            "*/investigation.md"
        )
    ):

        try:

            investigation = (
                parse_investigation(
                    investigation_file
                )
            )

        except (
            OSError,
            UnicodeError,
            ValueError,
        ):

            continue


        investigations.append({
            "name":
                investigation["name"],

            "title":
                investigation["title"],

            "status":
                investigation["status"],

            "source":
                investigation["source"],

            "captureMethod":
                investigation[
                    "captureMethod"
                ],

            "notebookUrl":
                investigation[
                    "notebookUrl"
                ],

            "summary":
                investigation["summary"],

            "currentStatus":
                investigation[
                    "currentStatus"
                ],

            "handoverSummary":
                investigation[
                    "handoverSummary"
                ],

            "supportingFiles":
                investigation[
                    "supportingFiles"
                ],
        })


    return investigations


def get_investigation(
    shift_date: str,
    investigation_name: str,
) -> dict | None:

    investigation_root = (
        NOC_ROOT
        / shift_date
        / "investigations"
    )


    if not investigation_root.is_dir():
        return None


    # Locate the investigation by exact directory name.
    # This avoids accepting path traversal input.
    matching_directory = None


    for candidate in (
        investigation_root.iterdir()
    ):

        if (
            candidate.is_dir()
            and candidate.name
            == investigation_name
        ):

            matching_directory = candidate

            break


    if matching_directory is None:
        return None


    investigation_file = (
        matching_directory
        / "investigation.md"
    )


    if not investigation_file.is_file():
        return None


    try:

        return parse_investigation(
            investigation_file
        )

    except (
        OSError,
        UnicodeError,
        ValueError,
    ):

        return None