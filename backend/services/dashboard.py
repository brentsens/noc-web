import json

from backend.config import NOC_ROOT


CLOSED_JIRA_STATUSES = {
    "done",
    "closed",
    "resolved",
}


def get_dashboard(shift_date: str) -> dict:

    shift_dir = NOC_ROOT / shift_date

    ticket_dir = (
        NOC_ROOT
        / "tickets"
        / "open"
    )

    investigation_dir = (
        shift_dir
        / "investigations"
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


    # Reviewed investigations

    investigation_files = []

    if investigation_dir.exists():
        investigation_files = list(
            investigation_dir.glob(
                "*/investigation.md"
            )
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
            len(ticket_files),

        "investigations":
            len(investigation_files),

        "needsReview":
            review_count,

        "handover": (
            "created"
            if handover_created
            else "pending"
        ),
    }

from datetime import date

from fastapi import (
    APIRouter,
    HTTPException,
)

from backend.services.dashboard import (
    get_dashboard,
)


router = APIRouter(
    prefix="/api/dashboard",
    tags=["dashboard"],
)


@router.get("/{shift_date}")
def dashboard(
    shift_date: str,
):

    try:

        date.fromisoformat(
            shift_date
        )

    except ValueError:

        raise HTTPException(
            status_code=400,
            detail=(
                "shift_date must use "
                "YYYY-MM-DD format"
            ),
        )


    return get_dashboard(
        shift_date
    )