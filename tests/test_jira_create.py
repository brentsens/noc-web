import subprocess

import pytest

from backend.services import jira_create


def test_build_description_template():
    description = (
        jira_create.build_description(
            tenant="Brinks US",
            customer="Valvoline",
            device="PB-03042",
            device_type="SmartSafe",
            device_id="2.73.PB03042",
            component="Validator",
            salesforce_ticket="00462126",
            issue_details=(
                "Bills are being rejected "
                "at a higher rate."
            ),
            technical_findings=(
                "No reject reason is available "
                "in current logs."
            ),
            steps=[
                "Open the device in SES.",
                "Review Expanded Status.",
                "Compare reject counters.",
            ],
        )
    )

    assert "**Customer Info:**" in description
    assert "Tenant: Brinks US" in description
    assert "Customer: Valvoline" in description
    assert "Device: PB-03042" in description

    assert (
        "**Summary of Request:**"
        in description
    )

    assert (
        "Bills are being rejected"
        in description
    )

    assert (
        "No reject reason is available"
        in description
    )

    assert (
        "**Steps to Reproduce:**"
        in description
    )

    assert (
        "1. Open the device in SES."
        in description
    )

    assert (
        "3. Compare reject counters."
        in description
    )


def test_preview_requires_summary():
    with pytest.raises(
        ValueError
    ):
        jira_create.preview_jira_ticket(
            "   ",
            "Description",
        )


def test_preview_requires_description():
    with pytest.raises(
        ValueError
    ):
        jira_create.preview_jira_ticket(
            "Test ticket",
            "   ",
        )


def test_preview_requires_atlas(
    monkeypatch,
):
    monkeypatch.setattr(
        jira_create.shutil,
        "which",
        lambda command: None,
    )

    with pytest.raises(
        FileNotFoundError
    ):
        jira_create.preview_jira_ticket(
            "Test ticket",
            "Description",
        )


def test_preview_always_uses_dry_run(
    monkeypatch,
):
    captured = {}

    monkeypatch.setattr(
        jira_create.shutil,
        "which",
        lambda command: "/mock/atlas",
    )

    def fake_run(
        args,
        **kwargs,
    ):
        captured["args"] = args

        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=(
                '{"dry_run":true}'
            ),
            stderr="",
        )

    monkeypatch.setattr(
        jira_create.subprocess,
        "run",
        fake_run,
    )

    result = (
        jira_create.preview_jira_ticket(
            "Test NOC ticket",
            "Test description",
        )
    )

    args = captured["args"]

    assert args[:3] == [
        "/mock/atlas",
        "jira",
        "create",
    ]

    assert "--project" in args
    assert "NOC" in args

    assert "--type" in args
    assert "SES" in args

    assert "--description" in args

    assert "--dry-run" in args

    assert result["created"] is False


def test_preview_failure_does_not_create(
    monkeypatch,
):
    monkeypatch.setattr(
        jira_create.shutil,
        "which",
        lambda command: "/mock/atlas",
    )

    monkeypatch.setattr(
        jira_create.subprocess,
        "run",
        lambda args, **kwargs:
            subprocess.CompletedProcess(
                args=args,
                returncode=1,
                stdout="",
                stderr="Jira preview failed",
            ),
    )

    with pytest.raises(
        RuntimeError
    ):
        jira_create.preview_jira_ticket(
            "Test ticket",
            "Test description",
        )

def test_create_never_uses_dry_run(
    monkeypatch,
):
    captured = {}

    monkeypatch.setattr(
        jira_create.shutil,
        "which",
        lambda command: "/mock/atlas",
    )

    def fake_run(
        args,
        **kwargs,
    ):
        captured["args"] = args

        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=(
                '{"key":"NOC-999",'
                '"browse_url":'
                '"https://example.test/browse/NOC-999"}'
            ),
            stderr="",
        )

    monkeypatch.setattr(
        jira_create.subprocess,
        "run",
        fake_run,
    )

    result = jira_create.create_jira_ticket(
        "Test ticket",
        "Test description",
    )

    args = captured["args"]

    assert args[:3] == [
        "/mock/atlas",
        "jira",
        "create",
    ]

    assert "--dry-run" not in args
    assert "--description" in args

    assert result["created"] is True
    assert result["key"] == "NOC-999"


def test_create_requires_summary():
    with pytest.raises(
        ValueError
    ):
        jira_create.create_jira_ticket(
            "   ",
            "Description",
        )


def test_create_requires_description():
    with pytest.raises(
        ValueError
    ):
        jira_create.create_jira_ticket(
            "Test ticket",
            "   ",
        )


def test_create_requires_ticket_key(
    monkeypatch,
):
    monkeypatch.setattr(
        jira_create.shutil,
        "which",
        lambda command: "/mock/atlas",
    )

    monkeypatch.setattr(
        jira_create.subprocess,
        "run",
        lambda args, **kwargs:
            subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout='{"created":true}',
                stderr="",
            ),
    )

    with pytest.raises(
        RuntimeError,
        match="ticket key",
    ):
        jira_create.create_jira_ticket(
            "Test ticket",
            "Test description",
        )


def test_create_rejects_invalid_output(
    monkeypatch,
):
    monkeypatch.setattr(
        jira_create.shutil,
        "which",
        lambda command: "/mock/atlas",
    )

    monkeypatch.setattr(
        jira_create.subprocess,
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
        match="invalid Jira creation output",
    ):
        jira_create.create_jira_ticket(
            "Test ticket",
            "Test description",
        )