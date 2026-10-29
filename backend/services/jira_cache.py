import json
from datetime import datetime, timezone

from backend.config import NOC_ROOT


CACHE_FILE = (
    NOC_ROOT / ".jira-open-tickets.json"
)


def write_jira_cache(
    jira_result: dict,
) -> dict:

    tickets = jira_result.get(
        "tickets",
        []
    )

    refreshed_at = (
        datetime.now(timezone.utc)
        .isoformat()
    )

    cache = {
        "refreshedAt": refreshed_at,
        "count": len(tickets),
        "tickets": tickets,
    }

    CACHE_FILE.write_text(
        json.dumps(
            cache,
            indent=2,
        ),
        encoding="utf-8",
    )

    return cache


def read_jira_cache() -> dict | None:

    if not CACHE_FILE.is_file():
        return None

    try:
        cache = json.loads(
            CACHE_FILE.read_text(
                encoding="utf-8"
            )
        )

    except (
        OSError,
        json.JSONDecodeError,
    ):
        return None

    if not isinstance(cache, dict):
        return None

    if not isinstance(
        cache.get("tickets"),
        list,
    ):
        return None

    return cache