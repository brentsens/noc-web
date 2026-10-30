import json
from datetime import datetime, timedelta, timezone

from backend.config import NOC_ROOT


CACHE_FILE = (
    NOC_ROOT / ".jira-open-tickets.json"
)

CURRENT_CACHE_AGE = timedelta(
    minutes=30,
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
    return read_jira_cache_from(CACHE_FILE)


def read_jira_cache_from(cache_file) -> dict | None:

    if not cache_file.is_file():
        return None

    try:
        cache = json.loads(
            cache_file.read_text(
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


def get_jira_cache_health() -> dict:
    unavailable = {
        "available": False,
        "refreshedAt": None,
        "freshness": "unavailable",
    }

    cache = read_jira_cache()

    if cache is None:
        return unavailable

    refreshed_at = cache.get(
        "refreshedAt"
    )

    if not isinstance(refreshed_at, str):
        return unavailable

    try:
        refreshed_at_datetime = (
            datetime.fromisoformat(
                refreshed_at
            )
        )
    except ValueError:
        return unavailable

    if (
        refreshed_at_datetime.tzinfo is None
        or refreshed_at_datetime.utcoffset() is None
    ):
        return unavailable

    age = (
        datetime.now(timezone.utc)
        - refreshed_at_datetime
    )

    return {
        "available": True,
        "refreshedAt": refreshed_at,
        "freshness": (
            "current"
            if age < CURRENT_CACHE_AGE
            else "stale"
        ),
    }
