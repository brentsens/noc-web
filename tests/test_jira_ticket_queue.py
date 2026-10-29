from backend.services import jira_ticket_queue


def test_cached_queue_merges_tracked_ticket(
    monkeypatch,
):
    monkeypatch.setattr(
        jira_ticket_queue,
        "read_jira_cache",
        lambda: {
            "refreshedAt":
                "2099-12-31T20:00:00+00:00",
            "count": 1,
            "tickets": [
                {
                    "id": "NOC-555",
                    "summary":
                        "Missing transactions",
                    "status": "Support Team",
                    "priority": "Medium",
                    "assignee": "Test User",
                    "reporter":
                        "Brentsen Smith",
                    "updated":
                        "2099-12-31T20:00:00",
                    "browseUrl":
                        "https://example.test/browse/NOC-555",
                }
            ],
        },
    )

    monkeypatch.setattr(
        jira_ticket_queue,
        "get_open_tickets",
        lambda: [
            {
                "id": "NOC-555",
                "environment": "USPRI",
                "nextAction":
                    "Awaiting customer response",
                "notes": "Test NOC note",
                "lastSynced":
                    "2099-12-31T19:00:00",
                "needsReview": False,
            }
        ],
    )

    result = (
        jira_ticket_queue
        .get_jira_ticket_queue()
    )

    assert result["count"] == 1
    assert result["trackedCount"] == 1
    assert result["untrackedCount"] == 0
    assert result["cacheAvailable"] is True

    assert result["refreshedAt"] == (
        "2099-12-31T20:00:00+00:00"
    )

    ticket = result["tickets"][0]

    assert ticket["id"] == "NOC-555"
    assert ticket["tracked"] is True
    assert ticket["environment"] == "USPRI"

    assert ticket["nextAction"] == (
        "Awaiting customer response"
    )

    assert ticket["notes"] == (
        "Test NOC note"
    )

    assert ticket["lastSynced"] == (
        "2099-12-31T19:00:00"
    )


def test_cached_untracked_ticket_remains_visible(
    monkeypatch,
):
    monkeypatch.setattr(
        jira_ticket_queue,
        "read_jira_cache",
        lambda: {
            "refreshedAt":
                "2099-12-31T20:00:00+00:00",
            "count": 1,
            "tickets": [
                {
                    "id": "NOC-583",
                    "summary":
                        "Recycler validation issue",
                    "status": "Support Team",
                    "reporter": "Other User",
                }
            ],
        },
    )

    monkeypatch.setattr(
        jira_ticket_queue,
        "get_open_tickets",
        lambda: [],
    )

    result = (
        jira_ticket_queue
        .get_jira_ticket_queue()
    )

    assert result["count"] == 1
    assert result["trackedCount"] == 0
    assert result["untrackedCount"] == 1

    ticket = result["tickets"][0]

    assert ticket["id"] == "NOC-583"
    assert ticket["tracked"] is False
    assert ticket["environment"] == ""
    assert ticket["nextAction"] == ""
    assert ticket["notes"] == ""
    assert ticket["lastSynced"] is None


def test_jira_fields_override_local_copy(
    monkeypatch,
):
    monkeypatch.setattr(
        jira_ticket_queue,
        "read_jira_cache",
        lambda: {
            "count": 1,
            "tickets": [
                {
                    "id": "NOC-555",
                    "summary":
                        "Current Jira summary",
                    "status": "Support Team",
                    "priority": "High",
                    "assignee":
                        "Current Assignee",
                    "reporter":
                        "Brentsen Smith",
                }
            ],
        },
    )

    monkeypatch.setattr(
        jira_ticket_queue,
        "get_open_tickets",
        lambda: [
            {
                "id": "NOC-555",
                "summary":
                    "Old local summary",
                "status": "Escalated",
                "priority": "Low",
                "assignee": "Old Assignee",
                "environment": "USPRI",
                "nextAction": "Investigate",
                "notes": "Local note",
                "lastSynced": None,
                "needsReview": False,
            }
        ],
    )

    ticket = (
        jira_ticket_queue
        .get_jira_ticket_queue()
        ["tickets"][0]
    )

    assert ticket["summary"] == (
        "Current Jira summary"
    )

    assert ticket["status"] == (
        "Support Team"
    )

    assert ticket["priority"] == "High"

    assert ticket["assignee"] == (
        "Current Assignee"
    )

    assert ticket["environment"] == (
        "USPRI"
    )

    assert ticket["notes"] == (
        "Local note"
    )


def test_counts_mixed_cached_queue(
    monkeypatch,
):
    monkeypatch.setattr(
        jira_ticket_queue,
        "read_jira_cache",
        lambda: {
            "count": 3,
            "tickets": [
                {"id": "NOC-100"},
                {"id": "NOC-101"},
                {"id": "NOC-102"},
            ],
        },
    )

    monkeypatch.setattr(
        jira_ticket_queue,
        "get_open_tickets",
        lambda: [
            {
                "id": "NOC-100",
                "environment": "EU",
                "nextAction": "Review",
                "notes": "",
                "lastSynced": None,
                "needsReview": False,
            },
            {
                "id": "NOC-102",
                "environment": "USPRI",
                "nextAction": "Monitor",
                "notes": "",
                "lastSynced": None,
                "needsReview": False,
            },
        ],
    )

    result = (
        jira_ticket_queue
        .get_jira_ticket_queue()
    )

    assert result["count"] == 3
    assert result["trackedCount"] == 2
    assert result["untrackedCount"] == 1


def test_missing_cache_returns_empty_queue(
    monkeypatch,
):
    monkeypatch.setattr(
        jira_ticket_queue,
        "read_jira_cache",
        lambda: None,
    )

    def fail_discovery():
        raise AssertionError(
            "Cached read must not query Jira."
        )

    monkeypatch.setattr(
        jira_ticket_queue,
        "get_open_jira_tickets",
        fail_discovery,
    )

    result = (
        jira_ticket_queue
        .get_jira_ticket_queue()
    )

    assert result == {
        "count": 0,
        "trackedCount": 0,
        "untrackedCount": 0,
        "refreshedAt": None,
        "tickets": [],
        "cacheAvailable": False,
    }


def test_refresh_discovers_writes_and_merges(
    monkeypatch,
):
    discovered = {
        "count": 1,
        "tickets": [
            {
                "id": "NOC-555",
                "summary": "Fresh Jira data",
                "status": "Support Team",
            }
        ],
    }

    written = {}

    monkeypatch.setattr(
        jira_ticket_queue,
        "get_open_jira_tickets",
        lambda: discovered,
    )

    def fake_write(result):
        written["result"] = result

        return {
            "refreshedAt":
                "2099-12-31T20:00:00+00:00",
            "count": 1,
            "tickets": result["tickets"],
        }

    monkeypatch.setattr(
        jira_ticket_queue,
        "write_jira_cache",
        fake_write,
    )

    monkeypatch.setattr(
        jira_ticket_queue,
        "get_open_tickets",
        lambda: [
            {
                "id": "NOC-555",
                "environment": "USPRI",
                "nextAction": "Monitor",
                "notes": "Local note",
                "lastSynced": None,
                "needsReview": False,
            }
        ],
    )

    result = (
        jira_ticket_queue
        .refresh_jira_ticket_queue()
    )

    assert written["result"] == discovered
    assert result["cacheAvailable"] is True
    assert result["count"] == 1
    assert result["trackedCount"] == 1

    ticket = result["tickets"][0]

    assert ticket["summary"] == (
        "Fresh Jira data"
    )

    assert ticket["environment"] == (
        "USPRI"
    )

    assert ticket["nextAction"] == (
        "Monitor"
    )