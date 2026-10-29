import json
import shutil
import subprocess


PROJECT = "NOC"
ISSUE_TYPE = "SES"


def build_description(
    tenant: str,
    customer: str,
    device: str,
    device_type: str,
    device_id: str,
    component: str,
    salesforce_ticket: str,
    issue_details: str,
    technical_findings: str,
    steps: list[str],
) -> str:

    clean_steps = [
        step.strip()
        for step in steps
        if step.strip()
    ]

    step_text = "\n".join(
        f"{index}. {step}"
        for index, step in enumerate(
            clean_steps,
            start=1,
        )
    )

    summary_parts = [
        issue_details.strip(),
        technical_findings.strip(),
    ]

    summary = "\n\n".join(
        part
        for part in summary_parts
        if part
    )

    return (
        "**Customer Info:**\n"
        f"Tenant: {tenant.strip()}\n"
        f"Customer: {customer.strip()}\n"
        f"Device: {device.strip()}\n"
        f"Device Type: {device_type.strip()}\n"
        f"Device ID: {device_id.strip()}\n"
        f"Component: {component.strip()}\n"
        f"Salesforce ticket: {salesforce_ticket.strip()}\n\n"
        "**Summary of Request:**\n"
        f"{summary}\n\n"
        "**Steps to Reproduce:**\n"
        f"{step_text}"
    )


def preview_jira_ticket(
    summary: str,
    description: str,
) -> dict:

    clean_summary = summary.strip()

    if not clean_summary:
        raise ValueError(
            "Summary is required."
        )

    if not description.strip():
        raise ValueError(
            "Description is required."
        )

    atlas = shutil.which(
        "atlas"
    )

    if not atlas:
        raise FileNotFoundError(
            "atlas command not found"
        )

    args = [
        atlas,
        "jira",
        "create",
        "--project",
        PROJECT,
        "--type",
        ISSUE_TYPE,
        "--summary",
        clean_summary,
        "--description",
        description,
        "--dry-run",
    ]

    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip()
            or result.stdout.strip()
            or "Jira ticket preview failed"
        )

    return {
        "project": PROJECT,
        "issueType": ISSUE_TYPE,
        "summary": clean_summary,
        "description": description,
        "preview": result.stdout.strip(),
        "created": False,
    }

def create_jira_ticket(
    summary: str,
    description: str,
) -> dict:

    clean_summary = summary.strip()

    if not clean_summary:
        raise ValueError(
            "Summary is required."
        )

    if not description.strip():
        raise ValueError(
            "Description is required."
        )

    atlas = shutil.which(
        "atlas"
    )

    if not atlas:
        raise FileNotFoundError(
            "atlas command not found"
        )

    args = [
        atlas,
        "jira",
        "create",
        "--project",
        PROJECT,
        "--type",
        ISSUE_TYPE,
        "--summary",
        clean_summary,
        "--description",
        description,
    ]

    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip()
            or result.stdout.strip()
            or "Jira ticket creation failed"
        )

    try:
        response = json.loads(
            result.stdout
        )

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Atlas returned invalid Jira creation output."
        ) from error

    ticket_key = (
        response.get("key")
        or response.get("issue", {}).get("key")
    )

    browse_url = (
        response.get("browse_url")
        or response.get("url")
        or response.get(
            "issue",
            {}
        ).get("browse_url")
    )

    if not ticket_key:
        raise RuntimeError(
            (
                "Atlas completed but did not return "
                "the created Jira ticket key."
            )
        )

    return {
        "project": PROJECT,
        "issueType": ISSUE_TYPE,
        "key": ticket_key,
        "browseUrl": browse_url,
        "summary": clean_summary,
        "created": True,
    }

