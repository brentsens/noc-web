import re
import shutil
import subprocess

from datetime import datetime
from backend.config import NOC_ROOT
from backend.services.tickets import get_operational_work_summary
from backend.services.investigations import (
    get_investigations,
    get_noc_root,
    get_reviewed_findings,
)



SECTION_PATTERN = re.compile(
    r"^##\s+(.+?)\s*$",
    re.MULTILINE,
)

LOCAL_WORK_SECTION_PATTERN = re.compile(
    r"(?ms)^## Active Local NOC Work\s*$.*?(?=^##\s|\Z)"
)
INVESTIGATION_SECTION_PATTERN = re.compile(
    r"(?m)^##\s+(?:Investigation Updates|Investigations)\s*$",
    re.IGNORECASE,
)
JIRA_TICKET_PATTERN = re.compile(
    r"^\s*[-*]\s+(?:\*\*)?[A-Z][A-Z0-9]*-\d+\b"
)
JIRA_REVIEW_METADATA_PATTERN = re.compile(
    r"operator[- ]reviewed finding|reviewed investigation context|"
    r"investigation review (?:records?|state|metadata)|"
    r"review(?:ed)? state|reviewed by|reviewed at|finding\s*:|"
    r"reviewState\s*:|reviewedAt\s*:|reviewedBy\s*:|"
    r"^\s*(?:[-*]\s*)?state\s*:\s*(?:cured|done|resolved|complete|completed|"
    r"closed|fixed|recovered)\b|"
    r"^\s*(?:[-*]\s*)?(?:investigation(?: name)?|display title|evidence provenance|"
    r"capture method|shift date|source of truth)\s*:|"
    r"notebook\s*:|app\.datadoghq\.com/notebook",
    re.IGNORECASE,
)
RESOLVED_STATE_PATTERN = re.compile(
    r"^(?:cured|done|resolved|complete|completed|closed|fixed|recovered|"
    r"cleared|remediated|fully cured|fully resolved|self-recovered)$",
    re.IGNORECASE,
)
ACTIVE_STATE_PATTERN = re.compile(
    r"^(?:active|open|ongoing|in progress|investigating|monitoring|escalated|unresolved|"
    r"follow-up required|follow up required)$",
    re.IGNORECASE,
)
MONITORING_FOLLOWUP_PATTERN = re.compile(
    r"\b(?:monitor|monitoring|alert|threshold|retry|retries|load balancer|"
    r"datadog|flapping)\b",
    re.IGNORECASE,
)
UNRESOLVED_INVESTIGATIONS_PATTERN = re.compile(
    r"\b\w+\s+reviewed investigations?\s+remains? unresolved"
    r"(?:\s*:\s*[\s\S]*?)?"
    r"(?:\.(?=\s+[A-Z0-9])|$)",
    re.IGNORECASE,
)
UNRESOLVED_COUNT_PATTERN = re.compile(
    r"\b(?P<count>one|two|three|four|five|both|all|these|\d+)\s+"
    r"(?:(?:earlier|prior|previous)\s+)?investigations?\s+remains? unresolved"
    r"(?:\s*:\s*[\s\S]*?)?"
    r"(?:\.(?=\s+[A-Z0-9])|$)",
    re.IGNORECASE,
)
SUMMARY_INVESTIGATION_CONFLICT_PATTERN = re.compile(
    r"\b(?:unresolved|needs?\s+operator\s+review|requires?\s+operator\s+review|"
    r"awaiting\s+(?:operator\s+)?review|advisory.{0,60}operator\s+review)\b",
    re.IGNORECASE,
)
SUMMARY_SENTENCE_SEPARATOR_PATTERN = re.compile(
    r"(?<=[.!?])(\s+)(?=[A-Z0-9])"
)
INVESTIGATION_ACTION_STOP_WORDS = {
    "a", "an", "and", "at", "by", "failure", "for", "from", "in",
    "investigation", "of", "on", "or", "parse", "stuck", "the", "to",
    "uspri", "prod",
}


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


def _section_matches(content: str):
    return list(SECTION_PATTERN.finditer(content))


def _section_bounds(content: str, section_name: str):
    matches = _section_matches(content)
    for index, match in enumerate(matches):
        if match.group(1).strip().casefold() == section_name.casefold():
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            if index + 1 == len(matches):
                closing = re.search(r"(?m)^Please tag me\b", content[match.end():])
                if closing:
                    end = match.end() + closing.start()
            return match, end
    return None


def _replace_section_body(
    content: str,
    section_match,
    section_end: int,
    body: str,
    *,
    remove_empty: bool = False,
) -> str:
    if body.strip():
        return (
            content[:section_match.end()]
            + "\n\n"
            + body.strip()
            + "\n\n"
            + content[section_end:].lstrip("\n")
        )
    if remove_empty:
        return content[:section_match.start()] + content[section_end:].lstrip("\n")
    return (
        content[:section_match.end()]
        + "\n\n"
        + content[section_end:].lstrip("\n")
    )


def _is_resolved_state(state: str) -> bool:
    normalized = " ".join(state.casefold().split())
    return bool(RESOLVED_STATE_PATTERN.fullmatch(normalized))


def _is_active_state(state: str) -> bool:
    normalized = " ".join(state.casefold().split())
    return bool(ACTIVE_STATE_PATTERN.fullmatch(normalized))


def _investigation_keywords(investigation: dict) -> set[str]:
    title = investigation.get("displayTitle") or investigation.get("title") or ""
    name = investigation.get("name", "")
    words = re.findall(r"[a-z0-9]+", f"{title} {name}".casefold())
    return {
        word for word in words
        if len(word) > 2 and not word.isdigit() and word not in INVESTIGATION_ACTION_STOP_WORDS
    }


def _matches_investigation(text: str, investigations: list[dict]) -> bool:
    words = set(re.findall(r"[a-z0-9]+", text.casefold()))
    for investigation in investigations:
        keywords = _investigation_keywords(investigation)
        if len(words & keywords) >= min(2, len(keywords)):
            return True
    return False


def _generated_investigation_action_words(investigations: list[dict]) -> set[str]:
    words = set()
    for investigation in investigations:
        content = investigation.get("advisory", {}).get("content") or ""
        match = re.search(
            r"(?ms)^##\s+Next Actions\s*$([\s\S]*?)(?=^##\s|\Z)",
            content,
        )
        if not match:
            continue
        for action in re.findall(r"(?m)^\s*(?:[-*]|\d+\.)\s+(.+)$", match.group(1)):
            action_words = re.findall(r"[a-z0-9]+", action.casefold())
            words.update(
                word[:-1] if word.endswith("s") else word
                for word in action_words
                if len(word) > 2 and word not in INVESTIGATION_ACTION_STOP_WORDS
            )
    return words


def _matches_generated_investigation_action(text: str, action_words: set[str]) -> bool:
    if JIRA_TICKET_PATTERN.match(text):
        return False
    words = {
        word[:-1] if word.endswith("s") else word
        for word in re.findall(r"[a-z0-9]+", text.casefold())
        if len(word) > 2 and word not in INVESTIGATION_ACTION_STOP_WORDS
    }
    return len(words & action_words) >= 3


def _canonical_investigation_section(content: str, investigations: list[dict]) -> str:
    section_match = INVESTIGATION_SECTION_PATTERN.search(content)
    if section_match is None and not investigations:
        return content
    if section_match is None:
        insertion = re.search(
            r"(?m)^##\s+(?:Monitoring & Alerting Improvements|Open Salesforce Tickets|"
            r"Open Jira Tickets|Next Shift Actions)\s*$",
            content,
        )
        if insertion is None:
            insertion = re.search(r"(?m)^Please tag me\b", content)
        insertion_index = insertion.start() if insertion else len(content)
        content = (
            content[:insertion_index].rstrip()
            + "\n\n## Investigation Updates\n"
            + content[insertion_index:]
        )
        section_match = INVESTIGATION_SECTION_PATTERN.search(content)
        if section_match is None:
            raise RuntimeError("Could not add the investigation section to the handover.")

    section_matches = _section_matches(content)
    next_section = next(
        (match for match in section_matches if match.start() > section_match.start()),
        None,
    )
    section_end = next_section.start() if next_section else len(content)
    if next_section is None:
        closing = re.search(r"(?m)^Please tag me\b", content[section_match.end():])
        if closing:
            section_end = section_match.end() + closing.start()

    lines = []
    for investigation in investigations:
        reviewed = investigation["reviewedFinding"]
        title = (
            investigation.get("displayTitle")
            or investigation.get("title")
            or investigation["name"]
        )
        lines.append(
            f"- **{title}** — Operator-reviewed finding: {reviewed['finding']}; "
            f"state: {reviewed['state']}."
        )
        reference = investigation.get("evidence", {}).get("reference")
        if reference:
            lines.append(f"  - Notebook: {reference}")
    return _replace_section_body(
        content,
        section_match,
        section_end,
        "\n".join(lines),
        remove_empty=not investigations,
    )


def _sanitize_open_jira_section(content: str, investigations: list[dict]) -> str:
    bounds = _section_bounds(content, "Open Jira Tickets")
    if bounds is None:
        return content
    section_match, section_end = bounds
    body = content[section_match.end():section_end]
    lines = []
    in_ticket = False
    for line in body.splitlines():
        if JIRA_REVIEW_METADATA_PATTERN.search(line):
            continue
        if JIRA_TICKET_PATTERN.match(line):
            in_ticket = True
            lines.append(line)
        elif _matches_investigation(line, investigations):
            continue
        elif re.match(r"^\s*[-*]\s+", line):
            if in_ticket and line[:1].isspace():
                lines.append(line)
            else:
                in_ticket = False
        elif re.match(r"^\s*No open Jira tickets\.?\s*$", line, re.IGNORECASE):
            in_ticket = False
            lines.append(line)
        elif not line.strip():
            if in_ticket:
                lines.append(line)
        elif in_ticket and line[:1].isspace():
            lines.append(line)
        else:
            in_ticket = False
    return _replace_section_body(content, section_match, section_end, "\n".join(lines))


def _filter_next_shift_actions(content: str, investigations: list[dict]) -> str:
    bounds = _section_bounds(content, "Next Shift Actions")
    if bounds is None:
        return content
    section_match, section_end = bounds
    body = content[section_match.end():section_end]
    generated_action_words = _generated_investigation_action_words(investigations)
    lines = body.splitlines()
    filtered = []
    current_group = []

    def flush_group():
        if not current_group:
            return
        is_ticket_group = bool(JIRA_TICKET_PATTERN.match(current_group[0]))
        if is_ticket_group:
            filtered.extend(current_group)
        elif not _matches_investigation(current_group[0], investigations) and not (
            _matches_generated_investigation_action(
                current_group[0],
                generated_action_words,
            )
        ):
            filtered.extend(
                line for line in current_group
                if not _matches_investigation(line, investigations)
                and not _matches_generated_investigation_action(
                    line,
                    generated_action_words,
                )
            )
        current_group.clear()

    for line in lines:
        if line.startswith("- "):
            flush_group()
            current_group.append(line)
        elif line.startswith("  ") and current_group:
            current_group.append(line)
        else:
            flush_group()
            if (
                not _matches_investigation(line, investigations)
                and not _matches_generated_investigation_action(
                    line,
                    generated_action_words,
                )
            ):
                filtered.append(line)
    flush_group()
    return _replace_section_body(content, section_match, section_end, "\n".join(filtered))


def _append_active_reviewed_actions(content: str, investigations: list[dict]) -> str:
    bounds = _section_bounds(content, "Next Shift Actions")
    if bounds is None:
        return content
    section_match, section_end = bounds
    actions = []
    for investigation in investigations:
        reviewed = investigation.get("reviewedFinding")
        if (
            investigation.get("lifecycle", {}).get("reviewState") != "reviewed"
            or not reviewed
            or not _is_active_state(reviewed["state"])
        ):
            continue
        title = (
            investigation.get("displayTitle")
            or investigation.get("title")
            or investigation["name"]
        )
        actions.append(
            f"- **{title}**: Operator-reviewed follow-up: {reviewed['finding']}"
        )
    if not actions:
        return content
    body = content[section_match.end():section_end].rstrip()
    return _replace_section_body(
        content,
        section_match,
        section_end,
        "\n".join(part for part in (body, *actions) if part),
    )


def _operator_monitoring_updates(shift_date: str) -> list[str]:
    notes_file = get_noc_root() / shift_date / "shift-notes.md"
    if not notes_file.is_file():
        return []
    notes = notes_file.read_text(encoding="utf-8")
    bounds = _section_bounds(notes, "Changes / Monitor Updates")
    if bounds is None:
        return []
    section_match, section_end = bounds
    body = notes[section_match.end():section_end]
    return [
        line.rstrip()
        for line in body.splitlines()
        if line.strip()
        and line.strip().casefold() not in {"none", "no changes", "no monitor updates"}
    ]


def _active_reviewed_monitoring_updates(investigations: list[dict]) -> list[str]:
    updates = []
    for investigation in investigations:
        reviewed = investigation.get("reviewedFinding")
        if (
            investigation.get("lifecycle", {}).get("reviewState") != "reviewed"
            or not reviewed
            or not _is_active_state(reviewed["state"])
            or not MONITORING_FOLLOWUP_PATTERN.search(reviewed["finding"])
        ):
            continue
        title = (
            investigation.get("displayTitle")
            or investigation.get("title")
            or investigation["name"]
        )
        updates.append(
            f"- **{title}**: Operator-reviewed follow-up: {reviewed['finding']}"
        )
    return updates


def _canonical_monitoring_improvements(
    content: str,
    shift_date: str,
    investigations: list[dict],
) -> str:
    updates = _operator_monitoring_updates(shift_date)
    updates.extend(_active_reviewed_monitoring_updates(investigations))
    bounds = _section_bounds(content, "Monitoring & Alerting Improvements")
    if bounds is not None:
        section_match, section_end = bounds
        return _replace_section_body(
            content,
            section_match,
            section_end,
            "\n".join(updates),
            remove_empty=not updates,
        )
    if not updates:
        return content

    insertion = re.search(
        r"(?m)^##\s+(?:Open Salesforce Tickets|Open Jira Tickets|Next Shift Actions)\s*$",
        content,
    )
    insertion_index = insertion.start() if insertion else len(content)
    section = "## Monitoring & Alerting Improvements\n\n" + "\n".join(updates)
    return (
        content[:insertion_index].rstrip()
        + "\n\n"
        + section
        + "\n\n"
        + content[insertion_index:].lstrip("\n")
    )


def _correct_resolved_investigation_summary(content: str, investigations: list[dict]) -> str:
    bounds = _section_bounds(content, "Summary")
    if bounds is None:
        return content
    resolved = [
        investigation for investigation in investigations
        if investigation.get("lifecycle", {}).get("reviewState") == "reviewed"
        and investigation.get("reviewedFinding")
        and _is_resolved_state(investigation["reviewedFinding"]["state"])
    ]
    if not resolved:
        return content

    all_investigations_resolved = bool(investigations) and all(
        investigation.get("lifecycle", {}).get("reviewState") == "reviewed"
        and investigation.get("reviewedFinding")
        and _is_resolved_state(investigation["reviewedFinding"]["state"])
        for investigation in investigations
    )

    def resolved_statements(items: list[dict]) -> str:
        statements = []
        for investigation in items:
            title = (
                investigation.get("displayTitle")
                or investigation.get("title")
                or investigation["name"]
            )
            state = investigation["reviewedFinding"]["state"]
            statements.append(f"Operator review marks {title} as {state}.")
        return " ".join(statements)

    section_match, section_end = bounds
    body = content[section_match.end():section_end]
    updated = UNRESOLVED_INVESTIGATIONS_PATTERN.sub(
        resolved_statements(resolved),
        body,
    )
    count_words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
    }

    def replace_unresolved_count(match) -> str:
        raw_count = match.group("count").casefold()
        count = (
            len(resolved)
            if raw_count in {"both", "all", "these"}
            else count_words.get(raw_count, int(raw_count) if raw_count.isdigit() else 0)
        )
        if all_investigations_resolved and count == len(resolved):
            return resolved_statements(resolved)
        return match.group(0)

    updated = UNRESOLVED_COUNT_PATTERN.sub(replace_unresolved_count, updated)
    sentences = SUMMARY_SENTENCE_SEPARATOR_PATTERN.split(updated)
    for index in range(0, len(sentences), 2):
        sentence = sentences[index]
        sentence_words = set(re.findall(r"[a-z0-9]+", sentence.casefold()))
        matching = [
            investigation for investigation in resolved
            if sentence_words & set(re.findall(
                r"[a-z0-9]+",
                (
                    investigation.get("displayTitle")
                    or investigation.get("title")
                    or investigation["name"]
                ).casefold(),
            ))
        ]
        if matching and "operator review marks" not in sentence.casefold():
            if SUMMARY_INVESTIGATION_CONFLICT_PATTERN.search(sentence):
                sentences[index] = resolved_statements(matching)
            else:
                sentences[index] = ""
    updated = re.sub(r"[ \t]{2,}", " ", "".join(sentences))
    missing_statuses = []
    for investigation in resolved:
        title = (
            investigation.get("displayTitle")
            or investigation.get("title")
            or investigation["name"]
        )
        state = investigation["reviewedFinding"]["state"]
        statement = f"Operator review marks {title} as {state}."
        if statement.casefold() not in updated.casefold():
            missing_statuses.append(statement)
    if missing_statuses:
        parts = SUMMARY_SENTENCE_SEPARATOR_PATTERN.split(updated)
        if len(parts) > 1:
            updated = (
                parts[0]
                + parts[1]
                + " ".join(missing_statuses)
                + " "
                + "".join(parts[2:])
            )
        else:
            updated = " ".join((updated.rstrip(), *missing_statuses))
        updated = re.sub(r"[ \t]{2,}", " ", updated)
    if updated != body:
        return _replace_section_body(content, section_match, section_end, updated)
    return content


def _include_reviewed_findings(handover_file, shift_date: str) -> None:
    investigations = get_investigations(shift_date)
    reviewed = [
        investigation for investigation in investigations
        if investigation.get("lifecycle", {}).get("reviewState") == "reviewed"
        and investigation.get("reviewedFinding") is not None
        and investigation.get("validationStatus") != "needs_review"
    ]

    content = handover_file.read_text(encoding="utf-8")
    content = _canonical_investigation_section(content, reviewed)
    content = _canonical_monitoring_improvements(
        content,
        shift_date,
        investigations,
    )
    content = _sanitize_open_jira_section(content, investigations)
    content = _filter_next_shift_actions(content, investigations)
    content = _append_active_reviewed_actions(content, reviewed)
    content = _correct_resolved_investigation_summary(content, investigations)
    handover_file.write_text(content, encoding="utf-8")


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
    _include_reviewed_findings(handover_file, shift_date)
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
        _include_reviewed_findings(handover_file, shift_date)
    except (OSError, RuntimeError):
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