import json

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