import json
from datetime import datetime, timedelta, timezone

from backend.services import jira_cache


def test_write_and_read_cache(
    noc_root,
    monkeypatch,
):
    cache_file = (
        noc_root
        / ".jira-open-tickets.json"
    )

    monkeypatch.setattr(
        jira_cache,
        "CACHE_FILE",
        cache_file,
    )

    source = {
        "count": 2,
        "tickets": [
            {
                "id": "NOC-100",
                "summary": "First",
            },
            {
                "id": "NOC-101",
                "summary": "Second",
            },
        ],
    }

    written = jira_cache.write_jira_cache(
        source
    )

    assert cache_file.is_file()
    assert written["count"] == 2
    assert len(written["tickets"]) == 2
    assert written["refreshedAt"]

    loaded = jira_cache.read_jira_cache()

    assert loaded == written


def test_missing_cache_returns_none(
    noc_root,
    monkeypatch,
):
    cache_file = (
        noc_root
        / ".jira-open-tickets.json"
    )

    monkeypatch.setattr(
        jira_cache,
        "CACHE_FILE",
        cache_file,
    )

    assert (
        jira_cache.read_jira_cache()
        is None
    )


def test_corrupt_cache_returns_none(
    noc_root,
    monkeypatch,
):
    cache_file = (
        noc_root
        / ".jira-open-tickets.json"
    )

    monkeypatch.setattr(
        jira_cache,
        "CACHE_FILE",
        cache_file,
    )

    cache_file.write_text(
        "not-json",
        encoding="utf-8",
    )

    assert (
        jira_cache.read_jira_cache()
        is None
    )


def test_invalid_cache_structure_returns_none(
    noc_root,
    monkeypatch,
):
    cache_file = (
        noc_root
        / ".jira-open-tickets.json"
    )

    monkeypatch.setattr(
        jira_cache,
        "CACHE_FILE",
        cache_file,
    )

    cache_file.write_text(
        json.dumps({
            "count": 1,
            "tickets": "invalid",
        }),
        encoding="utf-8",
    )

    assert (
        jira_cache.read_jira_cache()
        is None
    )


def test_cache_count_uses_ticket_list(
    noc_root,
    monkeypatch,
):
    cache_file = (
        noc_root
        / ".jira-open-tickets.json"
    )

    monkeypatch.setattr(
        jira_cache,
        "CACHE_FILE",
        cache_file,
    )

    result = jira_cache.write_jira_cache({
        "count": 999,
        "tickets": [
            {"id": "NOC-100"},
            {"id": "NOC-101"},
            {"id": "NOC-102"},
        ],
    })

    assert result["count"] == 3


def write_cache(
    cache_file,
    refreshed_at,
    tickets=None,
):
    cache_file.write_text(
        json.dumps({
            "refreshedAt": refreshed_at,
            "tickets": tickets or [],
        }),
        encoding="utf-8",
    )


def test_cache_health_is_current_for_valid_recent_cache(
    noc_root,
    monkeypatch,
):
    cache_file = noc_root / ".jira-open-tickets.json"
    monkeypatch.setattr(
        jira_cache,
        "CACHE_FILE",
        cache_file,
    )
    refreshed_at = (
        datetime.now(timezone.utc)
        - timedelta(minutes=29)
    ).isoformat()
    write_cache(cache_file, refreshed_at)

    assert jira_cache.get_jira_cache_health() == {
        "available": True,
        "refreshedAt": refreshed_at,
        "freshness": "current",
    }


def test_cache_health_is_stale_at_thirty_minutes(
    noc_root,
    monkeypatch,
):
    cache_file = noc_root / ".jira-open-tickets.json"
    monkeypatch.setattr(
        jira_cache,
        "CACHE_FILE",
        cache_file,
    )
    now = datetime(
        2026,
        10,
        30,
        tzinfo=timezone.utc,
    )
    refreshed_at = (
        now - timedelta(minutes=30)
    ).isoformat()
    write_cache(cache_file, refreshed_at)

    class FixedDatetime:

        @classmethod
        def fromisoformat(cls, value):
            return datetime.fromisoformat(value)

        @classmethod
        def now(cls, tz):
            return now

    monkeypatch.setattr(
        jira_cache,
        "datetime",
        FixedDatetime,
    )

    assert jira_cache.get_jira_cache_health() == {
        "available": True,
        "refreshedAt": refreshed_at,
        "freshness": "stale",
    }


def test_cache_health_is_unavailable_for_missing_invalid_or_naive_timestamp(
    noc_root,
    monkeypatch,
):
    cache_file = noc_root / ".jira-open-tickets.json"
    monkeypatch.setattr(
        jira_cache,
        "CACHE_FILE",
        cache_file,
    )
    unavailable = {
        "available": False,
        "refreshedAt": None,
        "freshness": "unavailable",
    }

    assert jira_cache.get_jira_cache_health() == unavailable

    cache_file.write_text(
        "not-json",
        encoding="utf-8",
    )

    assert jira_cache.get_jira_cache_health() == unavailable

    for refreshed_at in (
        None,
        "not-a-timestamp",
        "2026-10-29T12:00:00",
    ):
        write_cache(cache_file, refreshed_at)

        assert (
            jira_cache.get_jira_cache_health()
            == unavailable
        )


def test_cache_health_is_unavailable_for_structurally_invalid_cache(
    noc_root,
    monkeypatch,
):
    cache_file = noc_root / ".jira-open-tickets.json"
    monkeypatch.setattr(
        jira_cache,
        "CACHE_FILE",
        cache_file,
    )
    write_cache(
        cache_file,
        datetime.now(timezone.utc).isoformat(),
        tickets="invalid",
    )

    assert jira_cache.get_jira_cache_health() == {
        "available": False,
        "refreshedAt": None,
        "freshness": "unavailable",
    }


def test_cache_health_does_not_write_cache(
    noc_root,
    monkeypatch,
):
    cache_file = noc_root / ".jira-open-tickets.json"
    monkeypatch.setattr(
        jira_cache,
        "CACHE_FILE",
        cache_file,
    )
    write_cache(
        cache_file,
        datetime.now(timezone.utc).isoformat(),
        tickets=[{"id": "NOC-100"}],
    )
    original_contents = cache_file.read_text(
        encoding="utf-8"
    )

    jira_cache.get_jira_cache_health()

    assert cache_file.read_text(
        encoding="utf-8"
    ) == original_contents
