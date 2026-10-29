import json
import re
import shutil

from backend.config import NOC_ROOT

from backend.services.jira_ticket_queue import (
    get_jira_ticket_queue,
)


CLOSED_JIRA_STATUSES = {
    "done",
    "closed",
    "resolved",
}

DEPENDENCIES = (
    "atlas",
    "jq",
    "copilot",
    "tix",
    "noc-start",
    "noc-inv",
    "noc-handover",
)


def get_status(shift_date: str) -> dict:
    shift_dir = NOC_ROOT / shift_date
    notes_file = shift_dir / "shift-notes.md"
    investigation_dir = shift_dir / "investigations"
    handover_file = (
        shift_dir
        / "handover"
        / f"handover-{shift_date}.md"
    )

    ticket_dir = (
        NOC_ROOT
        / "tickets"
        / "open"
    )

    # Shift
    shift_exists = shift_dir.is_dir()
    notes_exist = notes_file.is_file()
    note_lines = 0

    if notes_exist:
        try:
            note_lines = sum(
                1
                for line in notes_file.read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            )
        except OSError:
            note_lines = 0

    jira_queue = get_jira_ticket_queue()

    jira_tickets = jira_queue.get(
        "tickets",
        []
    )


    # Open tickets and needs-review checks
    tickets = []
    needs_review = []

    if ticket_dir.is_dir():
        for ticket_file in sorted(
            ticket_dir.glob("*.json")
        ):
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
                needs_review.append({
                    "id": ticket_file.stem,
                    "reason": "Invalid ticket JSON",
                })
                continue

            if not (
                isinstance(ticket, dict)
                and isinstance(
                    ticket.get("id"),
                    str,
                )
                and isinstance(
                    ticket.get("jira"),
                    dict,
                )
                and isinstance(
                    ticket.get("noc"),
                    dict,
                )
            ):
                needs_review.append({
                    "id": ticket_file.stem,
                    "reason": "Invalid ticket JSON",
                })
                continue

            ticket_id = ticket["id"]

            status = (
                ticket.get("jira", {})
                .get("status", "")
            )

            environment = (
                ticket.get("noc", {})
                .get("environment", "")
            )

            source = (
                ticket.get("metadata", {})
                .get("source", "")
            )

            next_action = (
                ticket.get("noc", {})
                .get("next_action", "")
            )

            tickets.append({
                "id": ticket_id,
                "status": status,
                "environment": environment,
                "source": source,
                "nextAction": next_action,
            })

            normalized_status = (
                status.strip().casefold()
            )

            if (
                normalized_status
                in CLOSED_JIRA_STATUSES
            ):
                needs_review.append({
                    "id": ticket_id,
                    "reason": (
                        f"Jira status is {status} "
                        "but ticket is still "
                        "locally open"
                    ),
                })

            if source in {
                "manual",
                "migrated-manual",
            }:
                needs_review.append({
                    "id": ticket_id,
                    "reason": (
                        "Jira fields are not "
                        f"Atlas-synced "
                        f"(source={source})"
                    ),
                })

            if re.fullmatch(
                r"20\d{2}-\d{2}-\d{2} "
                r"\d{2}:\d{2}:\d{2}",
                next_action,
            ):
                needs_review.append({
                    "id": ticket_id,
                    "reason": (
                        "Next Action looks like "
                        "a migrated timestamp: "
                        f"{next_action}"
                    ),
                })

    # Investigations
    investigations = []

    if investigation_dir.is_dir():
        for investigation_file in sorted(
            investigation_dir.glob(
                "*/investigation.md"
            )
        ):
            investigation_status = ""

            try:
                for line in (
                    investigation_file
                    .read_text(
                        encoding="utf-8"
                    )
                    .splitlines()
                ):
                    if line.startswith(
                        "- Status:"
                    ):
                        investigation_status = (
                            line.split(
                                ":",
                                1,
                            )[1].strip()
                        )
                        break
            except OSError:
                pass

            investigations.append({
                "name":
                    investigation_file
                    .parent.name,
                "status": (
                    investigation_status
                    or "status not recorded"
                ),
            })

    # Handover
    handover_created = (
        handover_file.is_file()
        and handover_file.stat().st_size > 0
    )

    # Dependencies
    dependencies = []

    for command in DEPENDENCIES:
        path = shutil.which(command)

        dependencies.append({
            "name": command,
            "available": path is not None,
            "path": path,
        })

    return {
        "shiftDate": shift_date,

        "shift": {
            "directoryExists": shift_exists,
            "notesAvailable": notes_exist,
            "notesLines": note_lines,
        },

        "openTickets": {
            "count": len(jira_tickets),
            "items": jira_tickets,
        },

        "needsReview": {
            "count": len(needs_review),
            "items": needs_review,
        },

        "investigations": {
            "count": len(investigations),
            "items": investigations,
        },

        "handover": {
            "created": handover_created,
        },

        "dependencies": dependencies,

        "readOnly": True,
    }