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
    r"source|context|assistant|unavailable|error)\b",
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
    provider_status: str = "unavailable",
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
        if item.get("availability") != "available":
            continue
        identifier = item["id"]
        summary = item.get("summary")
        if item["kind"] == "jira-cache" and isinstance(summary, dict):
            tickets = summary.get("tickets", [])
            facts.append({
                "text": f"The current Jira cache contains {len(tickets)} open ticket(s).",
                "evidenceIds": [identifier],
            })
            for ticket in tickets:
                jira = ticket["jira"]
                facts.append({
                    "text": (
                        f"{jira['id']} is {jira['status']} with priority "
                        f"{jira['priority']}."
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
        if item.get("availability") != "available":
            continue
        summary = item.get("summary")
        if item["kind"] == "jira-cache":
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
        available_evidence = [
            item for item in context
            if item.get("availability") == "available"
        ]
        available_ids = {item["id"] for item in available_evidence}
        if not available_ids or not _has_substantive_context(context):
            return _response(
                question.shift_date,
                "limited",
                context,
                limitations + ["Available selected-shift context is insufficient to answer this question."],
                facts=facts,
                reviewed_findings=reviewed_findings,
            )

        envelope = {
            "shiftDate": question.shift_date,
            "question": question.question,
            "evidence": [
                item for item in context
                if item.get("availability") == "available"
            ],
            "policy": (
                "Read-only advisory analysis. Return only aiObservations and recommendations. "
                "Use only available evidence IDs. Do not claim facts, create reviewed findings, "
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
            available_evidence,
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
