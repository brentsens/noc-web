import json
import subprocess

import pytest

from backend.services import jira_discovery


def test_single_page_results(
    monkeypatch,
):
    captured = {}

    monkeypatch.setattr(
        jira_discovery.shutil,
        "which",
        lambda command: "/mock/atlas",
    )

    def fake_run(args, **kwargs):
        captured["args"] = args

        payload = {
            "count": 1,
            "items": [
                {
                    "key": "NOC-555",
                    "summary": "Test issue",
                    "status": "Support Team",
                    "priority": "Medium",
                    "assignee": "Test User",
                    "reporter": "Reporter",
                    "updated": "2099-12-31T20:00:00",
                    "browse_url":
                        "https://example.test/browse/NOC-555",
                }
            ],
            "is_last": True,
        }

        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )

    monkeypatch.setattr(
        jira_discovery.subprocess,
        "run",
        fake_run,
    )

    result = (
        jira_discovery.get_open_jira_tickets()
    )

    assert result["count"] == 1
    assert len(result["tickets"]) == 1

    ticket = result["tickets"][0]

    assert ticket["id"] == "NOC-555"
    assert ticket["status"] == "Support Team"

    assert ticket["browseUrl"] == (
        "https://example.test/browse/NOC-555"
    )

    args = captured["args"]

    assert args[:3] == [
        "/mock/atlas",
        "jira",
        "search",
    ]

    assert "--limit" in args
    assert "50" in args

    jql_index = (
        args.index("--jql") + 1
    )

    jql = args[jql_index]

    assert "project = NOC" in jql

    assert (
        "statusCategory != Done"
        in jql
    )

    assert (
        "ORDER BY updated DESC"
        in jql
    )


def test_multiple_pages(
    monkeypatch,
):
    calls = []

    monkeypatch.setattr(
        jira_discovery.shutil,
        "which",
        lambda command: "/mock/atlas",
    )

    def fake_run(args, **kwargs):
        calls.append(args)

        if "--page-token" not in args:

            payload = {
                "items": [
                    {
                        "key": "NOC-100",
                        "summary": "First",
                        "status": "Open",
                    }
                ],
                "next_page_token": "PAGE2",
                "is_last": False,
            }

        else:

            payload = {
                "items": [
                    {
                        "key": "NOC-101",
                        "summary": "Second",
                        "status": "Open",
                    }
                ],
                "is_last": True,
            }

        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )

    monkeypatch.setattr(
        jira_discovery.subprocess,
        "run",
        fake_run,
    )

    result = (
        jira_discovery.get_open_jira_tickets()
    )

    assert result["count"] == 2

    assert [
        ticket["id"]
        for ticket in result["tickets"]
    ] == [
        "NOC-100",
        "NOC-101",
    ]

    assert len(calls) == 2

    assert "--page-token" in calls[1]
    assert "PAGE2" in calls[1]


def test_browse_url_mapping(
    monkeypatch,
):
    monkeypatch.setattr(
        jira_discovery.shutil,
        "which",
        lambda command: "/mock/atlas",
    )

    payload = {
        "items": [
            {
                "key": "NOC-200",
                "browse_url":
                    "https://example.test/browse/NOC-200",
            }
        ],
        "is_last": True,
    }

    monkeypatch.setattr(
        jira_discovery.subprocess,
        "run",
        lambda args, **kwargs:
            subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps(payload),
                stderr="",
            ),
    )

    result = (
        jira_discovery.get_open_jira_tickets()
    )

    assert (
        result["tickets"][0]["browseUrl"]
        == "https://example.test/browse/NOC-200"
    )


def test_empty_queue(
    monkeypatch,
):
    monkeypatch.setattr(
        jira_discovery.shutil,
        "which",
        lambda command: "/mock/atlas",
    )

    monkeypatch.setattr(
        jira_discovery.subprocess,
        "run",
        lambda args, **kwargs:
            subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps({
                    "items": [],
                    "is_last": True,
                }),
                stderr="",
            ),
    )

    result = (
        jira_discovery.get_open_jira_tickets()
    )

    assert result == {
        "count": 0,
        "tickets": [],
    }


def test_invalid_json(
    monkeypatch,
):
    monkeypatch.setattr(
        jira_discovery.shutil,
        "which",
        lambda command: "/mock/atlas",
    )

    monkeypatch.setattr(
        jira_discovery.subprocess,
        "run",
        lambda args, **kwargs:
            subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="not-json",
                stderr="",
            ),
    )

    with pytest.raises(
        RuntimeError,
        match="invalid Jira search output",
    ):
        jira_discovery.get_open_jira_tickets()


def test_atlas_failure(
    monkeypatch,
):
    monkeypatch.setattr(
        jira_discovery.shutil,
        "which",
        lambda command: "/mock/atlas",
    )

    monkeypatch.setattr(
        jira_discovery.subprocess,
        "run",
        lambda args, **kwargs:
            subprocess.CompletedProcess(
                args=args,
                returncode=5,
                stdout="",
                stderr="Jira unavailable",
            ),
    )

    with pytest.raises(
        RuntimeError,
        match="Jira unavailable",
    ):
        jira_discovery.get_open_jira_tickets()