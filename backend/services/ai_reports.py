import os
import re
import secrets
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import NOC_ROOT
from backend.services.assistant import validate_assistant_response
from backend.services.assistant_actions import AI_ACTIONS


SHIFT_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REPORT_TOKEN_LENGTH = 4
REPORT_NAME_PATTERN = re.compile(
    r"^ai-(?P<slug>shift-analysis|shift-summary|followups|handover-review)-"
    r"\d{8}T\d{12}Z-[0-9a-f]{8}\.md$"
)


class AIReportInvalidResult(ValueError):
    """The normalized assistant response does not satisfy the report contract."""


class AIReportPersistenceError(Exception):
    """A report could not be saved; details are intentionally redacted."""


REPORT_TYPES = {
    "shift-analysis": {
        "file": "ai-shift-analysis.md",
        "title": "Shift Analysis",
    },
    "shift-summary": {
        "file": "ai-shift-summary.md",
        "title": "Shift Summary",
    },
    "followups": {
        "file": "ai-followups.md",
        "title": "Follow-ups",
    },
    "handover-review": {
        "file": "ai-handover-review.md",
        "title": "Handover Review",
    },
}


def _reports_directory(shift_date: str) -> Path:
    if not isinstance(shift_date, str) or not SHIFT_DATE_PATTERN.fullmatch(shift_date):
        raise ValueError("Invalid shift date.")
    try:
        date.fromisoformat(shift_date)
    except ValueError:
        raise ValueError("Invalid shift date.") from None
    root = NOC_ROOT.resolve()
    shift_dir = root / shift_date
    reports_dir = shift_dir / "reports"
    if (
        shift_dir.is_symlink()
        or reports_dir.is_symlink()
        or not reports_dir.resolve(strict=False).is_relative_to(root)
    ):
        raise ValueError("Invalid shift path.")
    return reports_dir


def _valid_report_result(shift_date: str, response: object) -> dict[str, Any]:
    if (
        not validate_assistant_response(response, shift_date)
        or response.get("status") != "complete"
        or response.get("providerStatus") != "success"
    ):
        raise AIReportInvalidResult

    evidence = response["evidence"]
    if not isinstance(evidence, list):
        raise AIReportInvalidResult
    evidence_by_id = {}
    for item in evidence:
        allowed = {"id", "kind", "provenance", "availability", "reference", "freshness"}
        if (
            not isinstance(item, dict)
            or set(item) - allowed
            or not {"id", "kind", "provenance", "availability", "reference"} <= set(item)
            or not isinstance(item["id"], str)
            or not isinstance(item["kind"], str)
            or not isinstance(item["provenance"], str)
            or not isinstance(item["availability"], str)
            or item["availability"] not in {
                "available", "unavailable", "stale", "malformed", "conflicting"
            }
            or (
                item["reference"] is not None
                and not isinstance(item["reference"], str)
            )
            or (
                item.get("freshness") is not None
                and not isinstance(item["freshness"], str)
            )
            or item.get("freshness") not in {
                None, "current", "stale", "unavailable", "malformed"
            }
            or item["id"] in evidence_by_id
        ):
            raise AIReportInvalidResult
        evidence_by_id[item["id"]] = item

    category_specs = {
        "facts": {"text", "evidenceIds"},
        "reviewedFindings": {"text", "state", "evidenceIds"},
        "aiObservations": {"text", "evidenceIds"},
        "recommendations": {"text", "evidenceIds"},
    }
    for category, expected_item_keys in category_specs.items():
        items = response[category]
        if not isinstance(items, list):
            raise AIReportInvalidResult
        for item in items:
            if (
                not isinstance(item, dict)
                or not (
                    set(item) == expected_item_keys
                    or (
                        category == "recommendations"
                        and set(item) == expected_item_keys | {"route"}
                    )
                )
                or not isinstance(item.get("text"), str)
                or not item["text"].strip()
                or not isinstance(item.get("evidenceIds"), list)
                or not item["evidenceIds"]
                or any(
                    not isinstance(identifier, str)
                    or identifier not in evidence_by_id
                    or evidence_by_id[identifier]["availability"]
                    not in (
                        {"available"}
                        if category == "reviewedFindings"
                        else {"available", "stale"}
                    )
                    for identifier in item["evidenceIds"]
                )
            ):
                raise AIReportInvalidResult
            if category == "reviewedFindings" and not isinstance(item["state"], str):
                raise AIReportInvalidResult
            if category == "recommendations" and "route" in item:
                route = item["route"]
                allowed_routes = {
                    "Open Tickets": ("tickets.html", True),
                    "Open Investigations": ("investigations.html", True),
                    "Open Status": ("status.html", False),
                    "Open Dashboard": ("index.html", False),
                    "Open End Shift": ("end-shift.html", True),
                }
                route_label = route.get("label") if isinstance(route, dict) else None
                if (
                    not isinstance(route, dict)
                    or set(route) != {"label", "href", "requiresConfirmation"}
                    or not isinstance(route_label, str)
                    or route_label not in allowed_routes
                    or route.get("href")
                    != f"{allowed_routes[route_label][0]}?shift={shift_date}"
                    or route.get("requiresConfirmation")
                    is not allowed_routes[route_label][1]
                ):
                    raise AIReportInvalidResult
                if route["label"] == "Open Investigations" and not any(
                    evidence_by_id[identifier]["kind"] == "investigation"
                    and evidence_by_id[identifier]["provenance"]
                    in {"noc-inv", "copilot-mcp"}
                    and evidence_by_id[identifier]["availability"] == "available"
                    for identifier in item["evidenceIds"]
                ):
                    raise AIReportInvalidResult

    if (
        not isinstance(response["limitations"], list)
        or any(not isinstance(item, str) for item in response["limitations"])
    ):
        raise AIReportInvalidResult
    return response


def _item_lines(items: list[dict], *, reviewed: bool = False) -> list[str]:
    if not items:
        return ["- None."]
    lines = []
    for item in items:
        citations = ", ".join(item["evidenceIds"])
        state = f" (state: {item['state']})" if reviewed else ""
        lines.append(f"- {item['text']}{state} [evidence: {citations}]")
        if "route" in item:
            route = item["route"]
            confirmation = (
                "; existing confirmation required"
                if route["requiresConfirmation"]
                else ""
            )
            lines.append(
                f"  - Suggested workflow: {route['label']} "
                f"(`{route['href']}`{confirmation})."
            )
    return lines


def _render_action_report(
    shift_date: str,
    action_type: str,
    response: dict,
    generated_at: datetime,
) -> str:
    action = AI_ACTIONS[action_type]
    lines = [
        f"# AI Action Report: {action.title}",
        "",
        f"- Selected shift: {shift_date}",
        f"- AI Action: {action.title}",
        f"- Generated: {generated_at.isoformat()}",
        "- Provider: GitHub Copilot CLI",
        "- Status: Advisory / non-authoritative",
        "",
        "## Source-grounded facts",
        *_item_lines(response["facts"]),
        "",
        "## Operator-reviewed investigation findings",
        *_item_lines(response["reviewedFindings"], reviewed=True),
        "",
        "## AI-generated observations (advisory)",
        *_item_lines(response["aiObservations"]),
        "",
        "## Recommendations (advisory)",
        *_item_lines(response["recommendations"]),
        "",
        "## Evidence and source status",
    ]
    if response["evidence"]:
        for evidence in response["evidence"]:
            freshness = (
                f"; freshness: {evidence['freshness']}"
                if evidence.get("freshness") is not None
                else ""
            )
            lines.append(
                f"- `{evidence['id']}` ({evidence['kind']}; "
                f"{evidence['provenance']}): {evidence['availability']}{freshness}."
            )
    else:
        lines.append("- None.")
    lines.extend(["", "## Limitations"])
    if response["limitations"]:
        lines.extend(f"- {item}" for item in response["limitations"])
    else:
        lines.append("- None reported.")
    lines.extend([
        "",
        "This report contains validated Assistant output for human review. "
        "It is not authoritative operational state and does not change any record.",
        "",
    ])
    return "\n".join(lines)


def persist_ai_action_report(
    shift_date: str,
    action_type: str,
    response: object,
) -> dict:
    action = AI_ACTIONS.get(action_type)
    if action is None:
        raise AIReportInvalidResult
    normalized = _valid_report_result(shift_date, response)
    generated_at = datetime.now(timezone.utc)
    content = _render_action_report(
        shift_date,
        action_type,
        normalized,
        generated_at,
    )
    try:
        reports_dir = _reports_directory(shift_date)
        if not reports_dir.is_dir():
            raise OSError
    except (OSError, RuntimeError, ValueError):
        raise AIReportPersistenceError from None

    timestamp = generated_at.strftime("%Y%m%dT%H%M%S%fZ")
    for _ in range(10):
        try:
            token = secrets.token_hex(REPORT_TOKEN_LENGTH)
        except OSError:
            raise AIReportPersistenceError from None
        filename = f"ai-{action.report_slug}-{timestamp}-{token}.md"
        report_file = reports_dir / filename
        try:
            descriptor = os.open(
                report_file,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
        except FileExistsError:
            continue
        except OSError:
            raise AIReportPersistenceError from None

        try:
            with os.fdopen(
                descriptor,
                "w",
                encoding="utf-8",
                newline="\n",
            ) as output:
                output.write(content)
        except (OSError, UnicodeError):
            try:
                report_file.unlink(missing_ok=True)
            except OSError:
                raise AIReportPersistenceError from None
            raise AIReportPersistenceError from None
        return {
            "name": filename,
            "title": action.title,
            "file": filename,
            "available": True,
        }
    raise AIReportPersistenceError


def get_ai_reports(
    shift_date: str,
) -> list:

    try:
        reports_dir = _reports_directory(shift_date)
    except (OSError, RuntimeError, ValueError):
        return []

    reports = []


    if not reports_dir.is_dir():
        return reports


    for report_name, definition in (
        REPORT_TYPES.items()
    ):

        report_file = (
            reports_dir
            / definition["file"]
        )


        if report_file.is_symlink() or not report_file.is_file():
            continue


        reports.append({
            "name":
                report_name,

            "title":
                definition["title"],

            "file":
                definition["file"],

            "available":
                True,
        })

    for report_file in sorted(reports_dir.glob("ai-*.md"), reverse=True):
        match = REPORT_NAME_PATTERN.fullmatch(report_file.name)
        if (
            match is None
            or report_file.is_symlink()
            or not report_file.is_file()
        ):
            continue
        action = next(
            (
                definition
                for definition in AI_ACTIONS.values()
                if definition.report_slug == match.group("slug")
            ),
            None,
        )
        if action is not None:
            reports.append({
                "name": report_file.name,
                "title": action.title,
                "file": report_file.name,
                "available": True,
            })

    return reports


def get_ai_report(
    shift_date: str,
    report_name: str,
) -> dict | None:

    definition = REPORT_TYPES.get(report_name)
    if definition is not None:
        filename = definition["file"]
        title = definition["title"]
    else:
        match = (
            REPORT_NAME_PATTERN.fullmatch(report_name)
            if isinstance(report_name, str)
            else None
        )
        if match is None:
            return None
        action = next(
            (
                definition
                for definition in AI_ACTIONS.values()
                if definition.report_slug == match.group("slug")
            ),
            None,
        )
        if action is None:
            return None
        filename = report_name
        title = action.title

    try:
        reports_dir = _reports_directory(shift_date)
    except (OSError, RuntimeError, ValueError):
        return None
    report_file = reports_dir / filename


    try:
        is_safe_file = (
            not report_file.is_symlink()
            and report_file.is_file()
            and report_file.resolve().is_relative_to(reports_dir.resolve())
        )
    except (OSError, RuntimeError):
        return None
    if not is_safe_file:
        return None


    try:

        content = report_file.read_text(
            encoding="utf-8"
        ).strip()

    except (
        OSError,
        UnicodeError,
    ):

        return None


    return {
        "name":
            report_name,

        "title":
            title,

        "file":
            filename,

        "content":
            content,

        "available":
            True,
    }