import json

from backend.config import NOC_ROOT


TICKET_DIR = (
    NOC_ROOT
    / "tickets"
    / "open"
)


def read_ticket(ticket_file) -> dict:

    ticket = json.loads(
        ticket_file.read_text(
            encoding="utf-8"
        )
    )

    jira = ticket.get("jira", {})
    noc = ticket.get("noc", {})
    metadata = ticket.get("metadata", {})

    return {
        "id": ticket.get(
            "id",
            ticket_file.stem,
        ),

        "summary": jira.get(
            "summary",
            "",
        ),

        "description": jira.get(
            "description",
            "",
        ),

        "status": jira.get(
            "status",
            "",
        ),

        "assignee": jira.get(
            "assignee",
            "",
        ),

        "priority": jira.get(
            "priority",
            "",
        ),

        "environment": noc.get(
            "environment",
            "",
        ),

        "nextAction": noc.get(
            "next_action",
            "",
        ),

        "notes": noc.get(
            "notes",
            "",
        ),

        "source": metadata.get(
            "source",
            "",
        ),

        "created": metadata.get(
            "created",
            "",
        ),

        "lastSynced": metadata.get(
            "last_synced",
            "",
        ),

        "needsReview": (
            not noc.get(
                "next_action",
                "",
            ).strip()
        ),
    }


def get_open_tickets() -> list[dict]:

    if not TICKET_DIR.exists():
        return []

    tickets = []

    for ticket_file in sorted(
        TICKET_DIR.glob("*.json")
    ):

        try:

            tickets.append(
                read_ticket(
                    ticket_file
                )
            )

        except (
            OSError,
            json.JSONDecodeError,
        ):

            continue

    return tickets


def get_open_ticket(
    ticket_id: str,
) -> dict | None:

    ticket_file = (
        TICKET_DIR
        / f"{ticket_id}.json"
    )

    if not ticket_file.is_file():
        return None

    try:

        return read_ticket(
            ticket_file
        )

    except (
        OSError,
        json.JSONDecodeError,
    ):

        return None