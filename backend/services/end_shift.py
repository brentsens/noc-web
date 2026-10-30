from backend.config import NOC_ROOT
from backend.services.health import get_health
from backend.services.status import get_status
from backend.services.ticket_sync import (
    get_ticket_sync_state,
)
from backend.services.tickets import get_operational_work_summary
from backend.services.investigations import get_reviewed_findings


def get_end_shift_preflight(
    shift_date: str,
) -> dict:

    shift_dir = NOC_ROOT / shift_date

    notes_file = (
        shift_dir / "shift-notes.md"
    )

    handover_file = (
        shift_dir
        / "handover"
        / f"handover-{shift_date}.md"
    )


    status = get_status(
        shift_date
    )
    local_work = status.get("localWork")
    if local_work is None:
        local_work = get_operational_work_summary()

    health = get_health(
        shift_date
    )

    jira_sync = get_ticket_sync_state()

    jira_synced = (
        jira_sync["synced"]
        and jira_sync["success"]
        and jira_sync["completedAt"]
        is not None
    )


    workspace_exists = shift_dir.is_dir()

    notes_exist = notes_file.is_file()

    handover_exists = (
        handover_file.is_file()
        and handover_file.stat().st_size > 0
    )


    review_count = (
        status["needsReview"]["count"]
    )

    health_failed = (
        health["result"]["failed"]
    )

    health_warnings = (
        health["result"]["warnings"]
    )


    blockers = []
    warnings = []


    if not workspace_exists:
        blockers.append(
            "Shift workspace is missing."
        )


    if not notes_exist:
        blockers.append(
            "Shift notes are missing."
        )


    if review_count > 0:
        blockers.append(
            (
                f"{review_count} item(s) "
                "require operational review."
            )
        )


    if health_failed > 0:
        blockers.append(
            (
                f"{health_failed} automation "
                "health check(s) failed."
            )
        )


    if health_warnings > 0:
        warnings.append(
            (
                f"{health_warnings} automation "
                "health warning(s) detected."
            )
        )

    if not jira_synced:
        blockers.append(
            "A successful Jira sync is required."
        )

    ready = (
        len(blockers) == 0
    )


    return {
        "shiftDate": shift_date,

        "mode": "PREFLIGHT",

        "readOnly": True,

        "ready": ready,

        "workspace": {
            "exists": workspace_exists,
            "path": str(shift_dir),
        },

        "notes": {
            "exists": notes_exist,
            "path": str(notes_file),
        },

        "jiraSync": {
            "synced": jira_synced,
            "state": (
                "CHECKED"
                if jira_synced
                else "NOT CHECKED"
            ),
            "completedAt":
                jira_sync["completedAt"],
        },

        "tickets": {
            "open": (
                status["openTickets"]["count"]
            ),
            "needsReview": review_count,
        },

        "investigations": {
            "count": (
                status["investigations"]["count"]
            ),
        },

        "health": {
            "state": (
                health["result"]["health"]
            ),
            "passed": (
                health["result"]["passed"]
            ),
            "warnings": health_warnings,
            "failed": health_failed,
        },

        "handover": {
            "exists": handover_exists,
            "path": str(handover_file),
        },

        "blockers": blockers,

        "warnings": warnings,

        "generation": {
            "enabled": (
                ready
                and not handover_exists
            ),
            "message": (
                "Handover already exists."
                if handover_exists
                else (
                    "End Shift preflight passed."
                    if ready
                    else (
                        "Handover generation is "
                        "blocked until review items "
                        "are resolved."
                    )
                )
            ),
        },

        "localWork": local_work,
        "reviewedFindings": get_reviewed_findings(shift_date),
    }