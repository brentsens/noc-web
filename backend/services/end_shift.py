from backend.config import NOC_ROOT
from backend.services.health import get_health
from backend.services.status import get_status


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

    health = get_health(
        shift_date
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
    }