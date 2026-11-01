import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


_NOC_TOOL_PROBES = (
    ("tix", ("--help",), None),
    ("noc-start", ("--help",), None),
    ("noc-status", ("--help",), None),
    ("noc-inv", ("--contract-version",), "noc-inv-contract=1"),
    ("noc-handover", ("--help",), None),
)
TRUSTED_LINUXBREW_BIN = Path("/home/linuxbrew/.linuxbrew/Homebrew/bin")
REQUIRED_ATLAS_SITE_ALIAS = "sesamiio"


def _result(
    identifier: str,
    capability: str,
    status: str,
    impact: str,
    corrective_action: str,
) -> dict:
    return {
        "id": identifier,
        "category": "external",
        "capability": capability,
        "status": status,
        "required": False,
        "impact": impact,
        "correctiveAction": corrective_action,
        "checkedAt": datetime.now(timezone.utc).isoformat(),
    }


def _executable(command: str, noc_bin: Path, *, noc_tool: bool = False) -> str | None:
    candidate = noc_bin / command
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    if noc_tool:
        return None
    search_path = os.pathsep.join((
        str(noc_bin),
        str(TRUSTED_LINUXBREW_BIN),
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
    ))
    return shutil.which(command, path=search_path)


def _probe(
    executable: str,
    arguments: tuple[str, ...],
    timeout_seconds: int,
    *,
    expected_output: str | None = None,
) -> bool:
    try:
        result = subprocess.run(
            [executable, *arguments],
            shell=False,
            timeout=timeout_seconds,
            stdout=subprocess.PIPE if expected_output is not None else subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            text=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and (
        expected_output is None or result.stdout.strip() == expected_output
    )


def _atlas_auth_status(executable: str, timeout_seconds: int) -> str:
    try:
        result = subprocess.run(
            [executable, "auth", "status", "--json"],
            shell=False,
            timeout=timeout_seconds,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            text=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    if result.returncode != 0:
        return "unavailable"
    try:
        status = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError):
        return "unavailable"
    if not isinstance(status, dict):
        return "unavailable"
    session_usable = status.get("session_usable")
    signed_in = status.get("signed_in")
    sites = status.get("sites")
    if type(session_usable) is not bool or type(signed_in) is not bool:
        return "unavailable"
    if not isinstance(sites, list):
        return "unavailable"
    if not session_usable or not signed_in:
        return "setup_required"
    if any(
        isinstance(site, dict)
        and site.get("alias") == REQUIRED_ATLAS_SITE_ALIAS
        and site.get("usable") is True
        for site in sites
    ):
        return "ready"
    return "setup_required"


def assess_external_capabilities(
    noc_bin: Path,
    *,
    timeout_seconds: int,
) -> list[dict]:
    noc_bin = Path(noc_bin)
    results = []

    atlas = _executable("atlas", noc_bin)
    if atlas is None:
        results.append(_result(
            "external.atlas",
            "Atlas Jira access",
            "setup_required",
            "Jira refresh is unavailable because Atlas is not installed.",
            "Install and authenticate Atlas using its approved setup, then Recheck.",
        ))
    else:
        atlas_status = _atlas_auth_status(atlas, timeout_seconds)
        if atlas_status == "ready":
            results.append(_result(
                "external.atlas",
                "Atlas Jira access",
                "ready",
                "The authenticated Atlas session and Jira site access were verified.",
                "No action required.",
            ))
        elif atlas_status == "setup_required":
            results.append(_result(
                "external.atlas",
                "Atlas Jira access",
                "setup_required",
                "Jira refresh is unavailable because Atlas sign-in or site access needs setup.",
                "Sign in to Atlas and restore usable Jira site access, then Recheck.",
            ))
        else:
            results.append(_result(
                "external.atlas",
                "Atlas Jira access",
                "unavailable",
                "Jira refresh could not be verified; authentication or connectivity may be unavailable.",
                "Check Atlas authentication and availability, then Recheck.",
            ))

    copilot = _executable("copilot", noc_bin)
    copilot_probe_succeeded = (
        copilot is not None
        and _probe(copilot, ("--version",), timeout_seconds)
    )
    if copilot is None:
        copilot_status = "setup_required"
        copilot_impact = "AI Actions and Copilot-dependent workflows are unavailable."
        copilot_action = "Install and authenticate GitHub Copilot CLI using its approved setup, then Recheck."
    elif not copilot_probe_succeeded:
        copilot_status = "unavailable"
        copilot_impact = "GitHub Copilot CLI could not complete its bounded availability check."
        copilot_action = "Check GitHub Copilot CLI availability, then Recheck."
    else:
        copilot_status = "setup_required"
        copilot_impact = "The CLI is installed, but authentication is not safely verifiable."
        copilot_action = "Confirm Copilot CLI authentication using its approved setup, then Recheck."
    results.append(_result(
        "external.copilot",
        "GitHub Copilot CLI",
        copilot_status,
        copilot_impact,
        copilot_action,
    ))

    if copilot is None:
        datadog_status = "setup_required"
        datadog_impact = "Datadog MCP workflows require GitHub Copilot CLI."
        datadog_action = "Install Copilot CLI and configure Datadog MCP using approved setup, then Recheck."
    else:
        datadog_status = "setup_required"
        datadog_impact = "Datadog MCP configuration and authentication cannot be safely verified."
        datadog_action = "Verify the Datadog MCP server in Copilot configuration using approved setup, then Recheck."
    results.append(_result(
        "external.datadogMcp",
        "Datadog MCP",
        datadog_status,
        datadog_impact,
        datadog_action,
    ))

    m365 = _executable("m365", noc_bin)
    if m365 is None:
        results.append(_result(
            "external.microsoft365",
            "Microsoft 365 CLI",
            "setup_required",
            "Email preview and send are unavailable because Microsoft 365 CLI is not installed.",
            "Install and authenticate Microsoft 365 CLI using its approved setup, then Recheck.",
        ))
    elif _probe(m365, ("status",), timeout_seconds):
        results.append(_result(
            "external.microsoft365",
            "Microsoft 365 CLI",
            "ready",
            "The Microsoft 365 CLI status check completed successfully.",
            "No action required.",
        ))
    else:
        results.append(_result(
            "external.microsoft365",
            "Microsoft 365 CLI",
            "unavailable",
            "Microsoft 365 CLI authentication or availability could not be verified.",
            "Check Microsoft 365 CLI authentication and availability, then Recheck.",
        ))

    noc_tool_failures = []
    for command, arguments, expected_output in _NOC_TOOL_PROBES:
        executable = _executable(command, noc_bin, noc_tool=True)
        if executable is None or not _probe(
            executable,
            arguments,
            timeout_seconds,
            expected_output=expected_output,
        ):
            noc_tool_failures.append(command)
    if noc_tool_failures:
        results.append(_result(
            "external.nocTools",
            "noc-tools compatibility",
            "setup_required",
            "Workflows using one or more required noc-tools commands are unavailable.",
            "Restore the compatible noc-tools commands and run Recheck.",
        ))
    else:
        results.append(_result(
            "external.nocTools",
            "noc-tools compatibility",
            "ready",
            "Required noc-tools commands passed their bounded compatibility checks.",
            "No action required.",
        ))
    return results
