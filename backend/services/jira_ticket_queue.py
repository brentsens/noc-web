from backend.services.jira_cache import (
    read_jira_cache,
    write_jira_cache,
)
from backend.services.jira_discovery import (
    get_open_jira_tickets,
)
from backend.services.tickets import (
    get_open_tickets,
)


def _merge_ticket_queue(
    jira_result: dict,
) -> dict:

    local_tickets = get_open_tickets()

    local_by_id = {
        ticket["id"]: ticket
        for ticket in local_tickets
    }

    merged = []

    for jira_ticket in jira_result.get(
        "tickets",
        []
    ):
        ticket_id = jira_ticket["id"]

        local_ticket = local_by_id.get(
            ticket_id
        )

        merged_ticket = {
            **jira_ticket,
            "tracked":
                local_ticket is not None,

            "environment":
                (
                    local_ticket.get(
                        "environment",
                        "",
                    )
                    if local_ticket
                    else ""
                ),

            "nextAction":
                (
                    local_ticket.get(
                        "nextAction",
                        "",
                    )
                    if local_ticket
                    else ""
                ),

            "notes":
                (
                    local_ticket.get(
                        "notes",
                        "",
                    )
                    if local_ticket
                    else ""
                ),

            "lastSynced":
                (
                    local_ticket.get(
                        "lastSynced"
                    )
                    if local_ticket
                    else None
                ),

            "needsReview":
                (
                    local_ticket.get(
                        "needsReview",
                        False,
                    )
                    if local_ticket
                    else False
                ),
        }

        merged.append(
            merged_ticket
        )

    return {
        "count": len(merged),

        "trackedCount": sum(
            1
            for ticket in merged
            if ticket["tracked"]
        ),

        "untrackedCount": sum(
            1
            for ticket in merged
            if not ticket["tracked"]
        ),

        "refreshedAt":
            jira_result.get(
                "refreshedAt"
            ),

        "tickets": merged,
    }


def get_jira_ticket_queue() -> dict:

    cache = read_jira_cache()

    if cache is None:
        return {
            "count": 0,
            "trackedCount": 0,
            "untrackedCount": 0,
            "refreshedAt": None,
            "tickets": [],
            "cacheAvailable": False,
        }

    result = _merge_ticket_queue(
        cache
    )

    result["cacheAvailable"] = True

    return result


def refresh_jira_ticket_queue() -> dict:

    jira_result = get_open_jira_tickets()

    cache = write_jira_cache(
        jira_result
    )

    result = _merge_ticket_queue(
        cache
    )

    result["cacheAvailable"] = True

    return result