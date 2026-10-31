import json

from backend.config import NOC_ROOT
from backend.services.jira_ticket_queue import (
    get_jira_ticket_queue,
)
from backend.services.jira_cache import get_jira_cache_health
from backend.services.tickets import get_operational_work_summary
from backend.services.investigations import (
    get_investigations,
    get_noc_root,
    get_reviewed_findings,
)


CLOSED_JIRA_STATUSES = {
    "done",
    "closed",
    "resolved",
}


def get_dashboard(shift_date: str) -> dict:

    noc_root = get_noc_root()
    shift_dir = noc_root / shift_date

    jira_queue = get_jira_ticket_queue()

    jira_tickets = jira_queue.get(
        "tickets",
        []
    )

    ticket_dir = (
        noc_root
        / "tickets"
        / "open"
    )

    handover_file = (
        shift_dir
        / "handover"
        / f"handover-{shift_date}.md"
    )


    # Open locally tracked tickets

    ticket_files = []

    if ticket_dir.exists():
        ticket_files = list(
            ticket_dir.glob("*.json")
        )


    investigation_lifecycle = get_investigations(shift_date)
    investigation_review_count = sum(
        1
        for investigation in investigation_lifecycle
        if investigation.get("lifecycleStatus") == "ready_for_review"
        or investigation.get("error")
    )


    # Tickets requiring human review

    review_count = 0

    for ticket_file in ticket_files:

        try:

            ticket = json.loads(
                ticket_file.read_text(
                    encoding="utf-8"
                )
            )

        except (
            OSError,
            json.JSONDecodeError,
        ):

            review_count += 1
            continue


        jira_status = (
            ticket
            .get("jira", {})
            .get("status", "")
            .strip()
            .casefold()
        )


        if (
            jira_status
            in CLOSED_JIRA_STATUSES
        ):

            review_count += 1


    # Handover state

    handover_created = (
        handover_file.exists()
        and handover_file.is_file()
        and handover_file.stat().st_size > 0
    )


    return {
        "shiftDate": shift_date,

        "status": (
            "review"
            if review_count > 0
            else "ready"
        ),

        "openTickets":
            len(jira_tickets),

        "investigations":
            len(investigation_lifecycle),

        "investigationLifecycle":
            investigation_lifecycle,

        "investigationNeedsReview":
            investigation_review_count,

        "needsReview":
            review_count + investigation_review_count,

        "handover": (
            "created"
            if handover_created
            else "pending"
        ),
        "jiraCache": get_jira_cache_health(),
        "localWork": get_operational_work_summary(),
        "reviewedFindings": get_reviewed_findings(shift_date),
    }
