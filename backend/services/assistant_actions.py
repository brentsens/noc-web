from dataclasses import dataclass


@dataclass(frozen=True)
class AssistantAction:
    title: str
    question: str
    report_slug: str


AI_ACTIONS = {
    "analysis": AssistantAction(
        title="Analyze Entire Shift",
        question=(
            "Analyze the entire selected shift for operational patterns, risks, "
            "inconsistencies, unresolved work, stale information, and handover "
            "concerns. Explain implications supported by available evidence and "
            "keep all advice advisory."
        ),
        report_slug="shift-analysis",
    ),
    "summary": AssistantAction(
        title="Summarize Current Shift",
        question=(
            "Summarize the current selected shift concisely: meaningful activity, "
            "tracked work, investigations, outstanding items, and handover state. "
            "Distinguish source-grounded facts from analysis."
        ),
        report_slug="shift-summary",
    ),
    "followups": AssistantAction(
        title="Identify Follow-ups",
        question=(
            "Identify concrete follow-ups supported by the selected-shift evidence. "
            "Pay special attention to tracked tickets with a missing Next Action; "
            "explain why the gap matters and recommend review through an existing "
            "workflow without changing records."
        ),
        report_slug="followups",
    ),
    "handover": AssistantAction(
        title="Review Handover Draft",
        question=(
            "Assess the selected-shift handover draft for omissions, ambiguity, "
            "missing Next Actions, unresolved investigations, stale-source "
            "concerns, and handover readiness. Cite evidence for each issue and "
            "provide read-only advice."
        ),
        report_slug="handover-review",
    ),
}
