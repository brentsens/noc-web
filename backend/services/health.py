import json
import os
import shutil
import subprocess

from backend.config import NOC_ROOT


TOOLS = (
    "bash",
    "jq",
    "atlas",
    "copilot",
    "tix",
    "noc-start",
    "noc-status",
    "noc-inv",
    "noc-handover",
)

SCRIPTS = (
    "tix",
    "noc-start",
    "noc-status",
    "noc-inv",
    "noc-handover",
)


def get_health(shift_date: str) -> dict:
    checks = []
    passed = 0
    warnings = 0
    failed = 0

    def add_check(
        section: str,
        state: str,
        message: str,
    ):
        nonlocal passed
        nonlocal warnings
        nonlocal failed

        checks.append({
            "section": section,
            "state": state,
            "message": message,
        })

        if state == "pass":
            passed += 1
        elif state == "warning":
            warnings += 1
        else:
            failed += 1

    shift_dir = NOC_ROOT / shift_date
    notes_file = shift_dir / "shift-notes.md"
    ticket_dir = NOC_ROOT / "tickets" / "open"

    # Tools
    for command in TOOLS:
        path = shutil.which(command)

        if path:
            add_check(
                "Tools",
                "pass",
                f"{command}: {path}",
            )
        else:
            add_check(
                "Tools",
                "fail",
                f"{command} not found",
            )

    # Script Syntax
    for command in SCRIPTS:
        path = shutil.which(command)

        if not path:
            add_check(
                "Script Syntax",
                "warning",
                f"{command} skipped; command missing",
            )
            continue

        result = subprocess.run(
            ["bash", "-n", path],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            add_check(
                "Script Syntax",
                "pass",
                f"{command} syntax valid",
            )
        else:
            add_check(
                "Script Syntax",
                "fail",
                f"{command} syntax error: {path}",
            )

    # Storage
    if NOC_ROOT.is_dir():
        add_check(
            "Storage",
            "pass",
            f"{NOC_ROOT} exists",
        )
    else:
        add_check(
            "Storage",
            "fail",
            f"{NOC_ROOT} missing",
        )

    if (
        NOC_ROOT.is_dir()
        and os.access(NOC_ROOT, os.W_OK)
    ):
        add_check(
            "Storage",
            "pass",
            f"{NOC_ROOT} is writable",
        )
    else:
        add_check(
            "Storage",
            "fail",
            f"{NOC_ROOT} is not writable",
        )

    if ticket_dir.is_dir():
        add_check(
            "Storage",
            "pass",
            "Ticket directory exists",
        )
    else:
        add_check(
            "Storage",
            "warning",
            f"Ticket directory missing: {ticket_dir}",
        )

    if shift_dir.is_dir():
        add_check(
            "Storage",
            "pass",
            f"Shift directory exists: {shift_dir}",
        )
    else:
        add_check(
            "Storage",
            "warning",
            f"Shift directory missing: {shift_dir}",
        )

    if notes_file.is_file():
        add_check(
            "Storage",
            "pass",
            "Shift notes exist",
        )
    else:
        add_check(
            "Storage",
            "warning",
            f"Shift notes missing: {notes_file}",
        )

    # Ticket JSON Integrity
    jq_path = shutil.which("jq")

    if not jq_path:
        add_check(
            "Ticket JSON Integrity",
            "fail",
            "jq missing; cannot validate ticket records",
        )

    elif not ticket_dir.is_dir():
        add_check(
            "Ticket JSON Integrity",
            "warning",
            "No open-ticket directory to validate",
        )

    else:
        records = sorted(
            ticket_dir.glob("*.json")
        )

        if not records:
            add_check(
                "Ticket JSON Integrity",
                "pass",
                "No open JSON ticket records",
            )

        for ticket_file in records:
            name = ticket_file.name

            try:
                record = json.loads(
                    ticket_file.read_text(
                        encoding="utf-8"
                    )
                )
            except (
                OSError,
                json.JSONDecodeError,
            ):
                add_check(
                    "Ticket JSON Integrity",
                    "fail",
                    f"{name} is invalid JSON",
                )
                continue

            valid_structure = (
                isinstance(record, dict)
                and isinstance(
                    record.get("id"),
                    str,
                )
                and bool(record.get("id"))
                and isinstance(
                    record.get("jira"),
                    dict,
                )
                and isinstance(
                    record.get("noc"),
                    dict,
                )
                and isinstance(
                    record.get("metadata"),
                    dict,
                )
            )

            if valid_structure:
                add_check(
                    "Ticket JSON Integrity",
                    "pass",
                    f"{name} structure valid",
                )
            else:
                add_check(
                    "Ticket JSON Integrity",
                    "fail",
                    f"{name} missing required tix structure",
                )

            ticket_id = record.get(
                "id",
                "",
            )

            if ticket_id == ticket_file.stem:
                add_check(
                    "Ticket JSON Integrity",
                    "pass",
                    f"{name} ID matches filename",
                )
            else:
                add_check(
                    "Ticket JSON Integrity",
                    "fail",
                    (
                        f"{name} ID mismatch: "
                        f"record={ticket_id}"
                    ),
                )

    # Atlas / Jira
    if shutil.which("atlas"):
        add_check(
            "Atlas / Jira",
            "pass",
            "Atlas executable available",
        )

        add_check(
            "Atlas / Jira",
            "warning",
            (
                "Jira connectivity not tested in "
                "standard mode; use Atlas/tix "
                "during normal workflow"
            ),
        )
    else:
        add_check(
            "Atlas / Jira",
            "fail",
            "Atlas unavailable",
        )

    # Copilot
    if shutil.which("copilot"):
        add_check(
            "Copilot",
            "pass",
            "Copilot executable available",
        )

        add_check(
            "Copilot",
            "warning",
            (
                "Copilot/Datadog MCP network "
                "call intentionally not executed"
            ),
        )
    else:
        add_check(
            "Copilot",
            "fail",
            "Copilot unavailable",
        )

    # Operational Safety
    for command in SCRIPTS:
        path = shutil.which(command)

        if not path:
            continue

        try:
            permissions = (
                os.stat(path).st_mode & 0o777
            )
            permission_text = format(
                permissions,
                "03o",
            )
        except OSError:
            permission_text = "unknown"

        safe = (
            permission_text != "unknown"
            and permission_text[1] in "012345"
            and permission_text[2] in "012345"
        )

        if safe:
            add_check(
                "Operational Safety",
                "pass",
                (
                    f"{command} permissions: "
                    f"{permission_text}"
                ),
            )
        else:
            add_check(
                "Operational Safety",
                "warning",
                (
                    f"{command} permissions are "
                    f"{permission_text}; review "
                    "group/world write access"
                ),
            )

    if failed > 0:
        health = "UNHEALTHY"
    elif warnings > 0:
        health = "HEALTHY WITH WARNINGS"
    else:
        health = "HEALTHY"

    return {
        "shiftDate": shift_date,
        "mode": "STANDARD",
        "readOnly": True,
        "result": {
            "passed": passed,
            "warnings": warnings,
            "failed": failed,
            "health": health,
        },
        "checks": checks,
    }