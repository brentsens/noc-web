"""Transient advisory mediation; no request material is retained or logged."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from backend.services.assistant_context import VALID_AVAILABILITY, collect_context
from backend.services.copilot_mcp import (
    CopilotMcpAdapter,
    CopilotProvider,
    CopilotProviderInvalid,
    CopilotProviderTimeout,
    CopilotProviderUnavailable,
    ask_copilot,
)


QUESTION_MAX_LENGTH = 1000
ASSISTANT_PROVIDER = "github-copilot-cli"
SHIFT_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PROHIBITED_ACTION_PATTERNS = (
    re.compile(
        r"\b(?:create|edit|update|modify|change|write|close|reopen|delete|transition|"
        r"review|reject|start|end|generate|deliver|send)\s+"
        r"(?:(?:a|an|the|my|this|new)\s+)?"
        r"(?:jira\s+)?(?:ticket|local tracking|tracking record|investigation|"
        r"shift note|shift notes|shift|handover(?: summary| file| document)?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:close|reopen|delete|edit|update|modify|change|review|reject|"
        r"start|end|deliver|send)\s+(?:it|them|this|that)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:sync|synchronize|refresh)\s+(?:(?:the|my)\s+)?"
        r"(?:jira|cache|ticket queue|local tracking|investigation|shift notes)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:sync|synchronize|refresh)\s+(?:it|them|this|that|data|now)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:run|execute)\s+(?:(?:a|the)\s+)?(?:command|shell|terminal|script)\b"
        r"|\b(?:curl|shell|terminal)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:query|fetch|retrieve|search|modify|change|update)\s+"
        r"(?:(?:the|a|an)\s+)?(?:datadog|external system|external service|jira)\b"
        r"|\bmake\s+(?:an?\s+)?(?:datadog|external|jira)\s+(?:query|request)\b"
        r"|\b(?:datadog|external system|external service)\s+"
        r"(?:query|request|write|change|modification)\b",
        re.IGNORECASE,
    ),
)
OVERRIDE_PATTERN = re.compile(
    r"(ignore (?:previous|all|your)|prompt injection|system prompt|"
    r"reveal (?:instructions|prompt)|bypass)",
    re.IGNORECASE,
)
SUPPORTED_CONTEXT_PATTERN = re.compile(
    r"\b(?:noc|shift|ticket|jira|tracking|next action|investigation|investigations|"
    r"reviewed|finding|findings|datadog|handover|status|dashboard|readiness|warning|"
    r"notes|focus|priority|priorities|attention|operational|work|carry over|changed|"
    r"source|context|assistant|unavailable|error|activity|action|today|yesterday|"
    r"timeline|chronology|latest|recent|last)\b",
    re.IGNORECASE,
)
TIMELINE_QUESTION_PATTERN = re.compile(
    r"\b(?:last (?:recorded )?(?:action|activity)|latest (?:recorded )?(?:action|activity)|"
    r"most recent (?:action|activity)|what happened (?:today|this shift)|"
    r"what did .{1,40} (?:do|happen) (?:today|this shift)|when did|when was|"
    r"timeline|chronology|shift activity)\b",
    re.IGNORECASE,
)
TRACKED_TICKET_QUESTION_PATTERN = re.compile(
    r"\b(?:tracked tickets?|local(?:ly)? tracked|ticket(?:s)? need attention)\b",
    re.IGNORECASE,
)
STALE_EVIDENCE_QUALIFIER_PATTERN = re.compile(
    r"\bstale\b|\b(?:as of|at) (?:the )?last refresh\b",
    re.IGNORECASE,
)
ROUTES = {
    "tickets.html": ("Open Tickets", True),
    "investigations.html": ("Open Investigations", True),
    "status.html": ("Open Status", False),
    "index.html": ("Open Dashboard", False),
    "end-shift.html": ("Open End Shift", True),
}


@dataclass(frozen=True)
class AssistantQuestion:
    shift_date: str
    question: str
    provider_disclosure_acknowledged: bool


def validate_shift_date(value: str) -> str:
    if not isinstance(value, str) or not SHIFT_PATTERN.fullmatch(value):
        raise ValueError("shiftDate must use YYYY-MM-DD format.")
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("shiftDate must use YYYY-MM-DD format.") from error
    return value


def validate_question(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("question is required.")
    value = " ".join(value.split())
    if not value or len(value) > QUESTION_MAX_LENGTH:
        raise ValueError(f"question must contain 1 to {QUESTION_MAX_LENGTH} characters.")
    return value


def _public_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    public = []
    for item in evidence:
        public_item = {
            key: value
            for key, value in item.items()
            if key != "summary"
        }
        public.append(public_item)
    return public


def _response(
    shift_date: str,
    status: str,
    evidence: list[dict[str, Any]],
    limitations: list[str],
    *,
    facts: list[dict[str, Any]] | None = None,
    reviewed_findings: list[dict[str, Any]] | None = None,
    ai_observations: list[dict[str, Any]] | None = None,
    recommendations: list[dict[str, Any]] | None = None,
    provider_invoked: bool = False,
    provider_status: str = "not-invoked",
) -> dict[str, Any]:
    return {
        "shiftDate": shift_date,
        "status": status,
        "provider": ASSISTANT_PROVIDER,
        "providerInvoked": provider_invoked,
        "providerStatus": provider_status,
        "facts": facts or [],
        "reviewedFindings": reviewed_findings or [],
        "aiObservations": ai_observations or [],
        "recommendations": recommendations or [],
        "evidence": _public_evidence(evidence),
        "limitations": limitations,
    }


def _route(value: Any, shift_date: str) -> dict[str, Any] | None:
    if not isinstance(value, dict) or set(value) != {"label", "href", "requiresConfirmation"}:
        return None
    href = value["href"]
    if not isinstance(href, str) or "?" in href or "#" in href or href not in ROUTES:
        return None
    label, confirmation = ROUTES[href]
    if value["label"] != label or value["requiresConfirmation"] is not confirmation:
        return None
    return {
        "label": label,
        "href": f"{href}?shift={shift_date}",
        "requiresConfirmation": confirmation,
    }


def _typed_items(
    value: Any,
    evidence_ids: set[str],
    *,
    route_allowed: bool = False,
) -> list[dict[str, Any]] | None:
    if not isinstance(value, list):
        return None
    items = []
    for item in value:
        if not isinstance(item, dict) or set(item) - {"text", "evidenceIds", "route"}:
            return None
        text, ids = item.get("text"), item.get("evidenceIds")
        if not isinstance(text, str) or not text.strip() or not isinstance(ids, list) or not ids:
            return None
        if any(not isinstance(identifier, str) or identifier not in evidence_ids for identifier in ids):
            return None
        result = {"text": " ".join(text.split()), "evidenceIds": ids}
        if "route" in item:
            if not route_allowed or _route(item["route"], "") is None:
                return None
            result["route"] = item["route"]
        items.append(result)
    return items


def _validate_provider_result(
    result: Any,
    available_evidence_ids: set[str],
    shift_date: str,
    available_evidence: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]] | None:
    if not isinstance(result, dict) or set(result) != {"aiObservations", "recommendations"}:
        return None
    observations = _typed_items(result["aiObservations"], available_evidence_ids)
    recommendations = _typed_items(
        result["recommendations"],
        available_evidence_ids,
        route_allowed=True,
    )
    if observations is None or recommendations is None:
        return None
    evidence_by_id = {item["id"]: item for item in available_evidence}
    for item in observations + recommendations:
        cites_stale_evidence = any(
            evidence_by_id[identifier].get("availability") == "stale"
            for identifier in item["evidenceIds"]
        )
        if cites_stale_evidence and not STALE_EVIDENCE_QUALIFIER_PATTERN.search(item["text"]):
            return None
    for recommendation in recommendations:
        route = _route(recommendation.get("route"), shift_date)
        if route is None:
            return None
        if route["href"].startswith("investigations.html?") and not any(
            item.get("id") in recommendation["evidenceIds"]
            and item.get("kind") == "investigation"
            and item.get("provenance") in {"noc-inv", "copilot-mcp"}
            and item.get("availability") == "available"
            for item in available_evidence
        ):
            return None
        recommendation["route"] = route
    return {
        "aiObservations": observations,
        "recommendations": recommendations,
    }


def _source_facts(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    facts = []
    for item in evidence:
        availability = item.get("availability")
        if availability != "available" and not (
            item.get("kind") == "jira-cache" and availability == "stale"
        ):
            continue
        identifier = item["id"]
        summary = item.get("summary")
        if item["kind"] == "jira-cache" and isinstance(summary, dict):
            tickets = summary.get("tickets", [])
            stale = availability == "stale" or item.get("freshness") == "stale"
            if stale:
                facts.append({
                    "text": (
                        f"The stale Jira cache contains {len(tickets)} open ticket(s) "
                        "and may not reflect current Jira state."
                    ),
                    "evidenceIds": [identifier],
                })
            else:
                facts.append({
                    "text": f"The current Jira cache contains {len(tickets)} open ticket(s).",
                    "evidenceIds": [identifier],
                })
            for ticket in tickets:
                jira = ticket["jira"]
                facts.append({
                    "text": (
                        (
                            f"At the time of the stale cache, {jira['id']} had status "
                            f"{jira['status']} and priority {jira['priority']}."
                            if stale
                            else
                            f"{jira['id']} is {jira['status']} with priority "
                            f"{jira['priority']}."
                        )
                    ),
                    "evidenceIds": [identifier],
                })
        elif item["kind"] == "local-work" and isinstance(summary, list):
            for ticket in summary:
                action = ticket["nextAction"].strip()
                facts.append({
                    "text": (
                        f"{ticket['jiraKey']} is actively tracked locally and "
                        + (f"has Next Action: {action}." if action else "is missing a Next Action.")
                    ),
                    "evidenceIds": [identifier],
                })
        elif (
            item["kind"] == "investigations"
            and isinstance(summary, dict)
            and summary.get("count", 0) > 0
        ):
            facts.append({
                "text": (
                    f"{summary['count']} active investigation(s) are recorded for this shift."
                ),
                "evidenceIds": [identifier],
            })
        elif (
            item["kind"] == "shift-notes"
            and isinstance(summary, dict)
            and summary.get("activity")
        ):
            count = len(summary.get("activity", []))
            facts.append({
                "text": f"Shift Notes contain {count} activity entr{'y' if count == 1 else 'ies'}.",
                "evidenceIds": [identifier],
            })
    return facts


def _has_substantive_context(evidence: list[dict[str, Any]]) -> bool:
    for item in evidence:
        availability = item.get("availability")
        if availability not in {"available", "stale"}:
            continue
        summary = item.get("summary")
        if item["kind"] == "jira-cache":
            if availability == "available" or (
                isinstance(summary, dict) and summary.get("tickets")
            ):
                return True
        if item["kind"] == "local-work" and summary:
            return True
        if item["kind"] == "shift-notes" and summary and summary.get("activity"):
            return True
        if item["kind"] == "handover" and summary and summary.get("sections"):
            return True
        if item["kind"] == "investigations" and summary and summary.get("count", 0) > 0:
            return True
        if item["kind"] == "reviewed-findings" and summary:
            return True
        if item["kind"] == "dashboard" and summary and summary.get("needsReviewCount", 0) > 0:
            return True
        if item["kind"] == "status" and summary and summary.get("needsReview", {}).get("count", 0) > 0:
            return True
    return False


def _has_question_sufficient_context(
    question: str,
    evidence: list[dict[str, Any]],
) -> bool:
    if TIMELINE_QUESTION_PATTERN.search(question):
        return any(
            item.get("kind") == "shift-notes"
            and item.get("availability") == "available"
            and isinstance(item.get("summary"), dict)
            and item["summary"].get("activity")
            for item in evidence
        )

    if TRACKED_TICKET_QUESTION_PATTERN.search(question):
        local_work_available = any(
            item.get("kind") == "local-work"
            and item.get("availability") == "available"
            and isinstance(item.get("summary"), list)
            and item["summary"]
            for item in evidence
        )
        jira_has_tracked_tickets = any(
            item.get("kind") == "jira-cache"
            and item.get("availability") in {"available", "stale"}
            and isinstance(item.get("summary"), dict)
            and any(
                ticket.get("localTracking", {}).get("tracked") is True
                for ticket in item["summary"].get("tickets", [])
                if isinstance(ticket, dict)
                and isinstance(ticket.get("localTracking"), dict)
            )
            for item in evidence
        )
        return local_work_available or jira_has_tracked_tickets

    return _has_substantive_context(evidence)


def _selected_shift_not_initialized(evidence: list[dict[str, Any]]) -> bool:
    status = next(
        (
            item.get("summary")
            for item in evidence
            if item.get("id") == "status"
            and item.get("availability") == "available"
        ),
        None,
    )
    if not isinstance(status, dict):
        return False
    shift = status.get("shift", {})
    return (
        isinstance(shift, dict)
        and not shift.get("directoryExists", True)
        and not shift.get("notesAvailable", True)
    )


def _activity_gap_message(shift_date: str, evidence: list[dict[str, Any]]) -> str:
    parsed_date = date.fromisoformat(shift_date)
    date_label = f"{parsed_date.month}/{parsed_date.day}/{parsed_date.year}"
    if _selected_shift_not_initialized(evidence):
        notes_reason = "The selected shift has not been initialized and Shift Notes are unavailable."
    elif any(
        item.get("id") == "shift-notes"
        and item.get("availability") == "available"
        and isinstance(item.get("summary"), dict)
        and not item["summary"].get("activity")
        for item in evidence
    ):
        notes_reason = "Shift Notes contain no recorded activity for the selected shift."
    else:
        notes_reason = "Shift Notes are not available for the selected shift."
    return (
        f"No recorded shift activity is available for {date_label} yet. "
        f"{notes_reason} The last action taken for that shift cannot be determined "
        "from the bounded context."
    )


def _insufficient_context_reason(
    shift_date: str,
    question: str,
    evidence: list[dict[str, Any]],
) -> str:
    if TIMELINE_QUESTION_PATTERN.search(question):
        return _activity_gap_message(shift_date, evidence)
    if _selected_shift_not_initialized(evidence):
        return (
            "The selected shift has not been initialized and Shift Notes are unavailable. "
            "Available sources do not contain evidence sufficient to answer this question; "
            "the provider was not invoked."
        )
    return (
        "Available selected-shift context is insufficient to answer this question; "
        "the provider was not invoked."
    )


def _activity_gap_fact(
    shift_date: str,
    evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    source = next(
        (
            item for item in evidence
            if item.get("id") == "shift-notes"
            and item.get("availability") == "available"
        ),
        None,
    )
    if source is None:
        source = next(
            (
                item for item in evidence
                if item.get("id") == "status"
                and item.get("availability") == "available"
            ),
            None,
        )
    if source is None:
        return []
    return [{
        "text": _activity_gap_message(shift_date, evidence),
        "evidenceIds": [source["id"]],
    }]


def _reviewed_findings(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    for item in evidence:
        if item.get("kind") != "investigation" or item.get("availability") != "available":
            continue
        summary = item.get("summary")
        if not isinstance(summary, dict):
            continue
        finding = summary.get("reviewedFinding")
        if not isinstance(finding, dict):
            continue
        text = finding.get("finding")
        state = finding.get("state")
        if not isinstance(text, str) or not text or not isinstance(state, str):
            continue
        findings.append({
            "text": text,
            "state": state,
            "evidenceIds": [item["id"]],
        })
    return findings


def _limitation_messages(evidence: list[dict[str, Any]]) -> list[str]:
    return [
        f"{item['kind']} ({item['id']}) is {item['availability']}."
        for item in evidence
        if item.get("availability") != "available"
    ]


def _refusal(question: AssistantQuestion) -> dict[str, Any]:
    route = {
        "label": "Open Tickets",
        "href": f"tickets.html?shift={question.shift_date}",
        "requiresConfirmation": True,
    }
    return _response(
        question.shift_date,
        "limited",
        [],
        ["This request is outside the assistant's advisory boundary. Nothing was changed."],
        recommendations=[{
            "text": "Review the applicable existing workflow before deciding on an action.",
            "evidenceIds": [],
            "route": route,
        }],
    )


def answer(
    question: AssistantQuestion,
    provider: CopilotProvider | None = None,
) -> dict[str, Any]:
    """Answer one request and discard all temporary values before returning."""
    context: list[dict[str, Any]] | None = None
    envelope: dict[str, Any] | None = None
    provider_result: dict[str, Any] | None = None
    facts: list[dict[str, Any]] | None = None
    reviewed_findings: list[dict[str, Any]] | None = None
    try:
        if (
            any(pattern.search(question.question) for pattern in PROHIBITED_ACTION_PATTERNS)
            or OVERRIDE_PATTERN.search(question.question)
            or not SUPPORTED_CONTEXT_PATTERN.search(question.question)
        ):
            return _refusal(question)

        context = collect_context(question.shift_date)
        facts = _source_facts(context)
        reviewed_findings = _reviewed_findings(context)
        limitations = _limitation_messages(context)
        provider_evidence = [
            item for item in context
            if item.get("availability") in {"available", "stale"}
        ]
        available_ids = {item["id"] for item in provider_evidence}
        if not available_ids or not _has_question_sufficient_context(
            question.question,
            context,
        ):
            if TIMELINE_QUESTION_PATTERN.search(question.question):
                facts.extend(_activity_gap_fact(question.shift_date, context))
            return _response(
                question.shift_date,
                "limited",
                context,
                limitations + [
                    _insufficient_context_reason(
                        question.shift_date,
                        question.question,
                        context,
                    )
                ],
                facts=facts,
                reviewed_findings=reviewed_findings,
            )

        envelope = {
            "shiftDate": question.shift_date,
            "question": question.question,
            "evidence": provider_evidence,
            "policy": (
                "Read-only advisory analysis. Return only aiObservations and recommendations. "
                "Use only evidence IDs whose availability is available or stale. Clearly label "
                "stale evidence and never claim it represents current state. Do not claim facts, "
                "create reviewed findings, "
                "perform actions, use tools, execute commands, query external systems, or refresh data."
            ),
        }
        try:
            provider_result = (
                ask_copilot(envelope)
                if provider is None
                else CopilotMcpAdapter(provider).ask(envelope)
            )
        except CopilotProviderTimeout as error:
            return _response(
                question.shift_date,
                "unavailable",
                context,
                limitations + ["The assistant provider timed out. No AI advice was generated."],
                facts=facts,
                reviewed_findings=reviewed_findings,
                provider_invoked=error.provider_invoked,
                provider_status="timeout",
            )
        except CopilotProviderInvalid as error:
            return _response(
                question.shift_date,
                "unavailable",
                context,
                limitations + ["The assistant provider returned an invalid response. No AI advice was generated."],
                facts=facts,
                reviewed_findings=reviewed_findings,
                provider_invoked=error.provider_invoked,
                provider_status="invalid",
            )
        except CopilotProviderUnavailable as error:
            return _response(
                question.shift_date,
                "unavailable",
                context,
                limitations + ["The assistant provider is unavailable. No AI advice was generated."],
                facts=facts,
                reviewed_findings=reviewed_findings,
                provider_invoked=error.provider_invoked,
                provider_status="unavailable",
            )

        validated = _validate_provider_result(
            provider_result,
            available_ids,
            question.shift_date,
            provider_evidence,
        )
        if validated is None:
            return _response(
                question.shift_date,
                "unavailable",
                context,
                limitations + ["The assistant provider returned an invalid response. No AI advice was generated."],
                facts=facts,
                reviewed_findings=reviewed_findings,
                provider_invoked=True,
                provider_status="invalid",
            )
        return _response(
            question.shift_date,
            "complete",
            context,
            limitations,
            facts=facts,
            reviewed_findings=reviewed_findings,
            ai_observations=validated["aiObservations"],
            recommendations=validated["recommendations"],
            provider_invoked=True,
            provider_status="success",
        )
    finally:
        context = None
        envelope = None
        provider_result = None
        facts = None
        reviewed_findings = None
