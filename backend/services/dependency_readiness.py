import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from backend.services.ai_provider import provider_readiness


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
    installation_status: str | None = None,
) -> dict:
    return {
        "id": identifier,
        "category": "external",
        "capability": capability,
        "status": status,
        "installationStatus": installation_status or status,
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


def _probe_state(
    executable: str,
    arguments: tuple[str, ...],
    timeout_seconds: int,
) -> str:
    """Return a categorized probe outcome without retaining command output."""
    try:
        result = subprocess.run(
            [executable, *arguments],
            shell=False,
            timeout=timeout_seconds,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            text=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    if result.returncode != 0:
        return "setup_required"
    return "ready"


def _configured_mcp_state(
    executable: str,
    timeout_seconds: int,
    name: str,
) -> tuple[str, bool]:
    try:
        result = subprocess.run(
            [executable, "mcp", "list"],
            shell=False,
            timeout=timeout_seconds,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            text=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable", False
    if result.returncode != 0:
        return "setup_required", False
    return "ready", name.casefold() in result.stdout.casefold()


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
            "setup_required",
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
                "ready",
            ))
        elif atlas_status == "setup_required":
            results.append(_result(
                "external.atlas",
                "Atlas Jira access",
                "setup_required",
                "Jira refresh is unavailable because Atlas sign-in or site access needs setup.",
                "Sign in to Atlas and restore usable Jira site access, then Recheck.",
                "installed",
            ))
        else:
            results.append(_result(
                "external.atlas",
                "Atlas Jira access",
                "unavailable",
                "Jira refresh could not be verified; authentication or connectivity may be unavailable.",
                "Check Atlas authentication and availability, then Recheck.",
                "unavailable",
            ))

    copilot = _executable("copilot", noc_bin)
    provider = provider_readiness()
    provider_status = {
        "ready": "ready",
        "notReady": "setup_required",
        "notConfigured": "notConfigured",
    }[provider["readiness"]]
    provider_label = provider["label"] or "not configured"
    ai_provider = _result(
        "external.aiProvider",
        f"AI inference provider ({provider_label})",
        provider_status,
        provider["impact"],
        provider["correctiveAction"],
        provider_status,
    )
    ai_provider.update({
        "configuredProvider": provider["configuredProvider"],
        "model": provider["model"],
        "providerReadiness": provider["readiness"],
    })
    results.append(ai_provider)

    if copilot is None:
        copilot_status = "setup_required"
        copilot_installation_status = "setup_required"
        copilot_impact = "AI Actions and Copilot-dependent workflows are unavailable."
        copilot_action = "Install and authenticate GitHub Copilot CLI using its approved setup, then Recheck."
    elif _probe_state(copilot, ("--version",), timeout_seconds) != "ready":
        copilot_status = "unavailable"
        copilot_installation_status = "unavailable"
        copilot_impact = "GitHub Copilot CLI could not complete its bounded availability check."
        copilot_action = "Check GitHub Copilot CLI availability, then Recheck."
    else:
        copilot_status = _probe_state(copilot, ("auth", "status"), timeout_seconds)
        if copilot_status == "ready":
            copilot_installation_status = "ready"
            copilot_impact = "GitHub Copilot CLI availability and authentication were verified."
            copilot_action = "No action required."
        elif copilot_status == "setup_required":
            copilot_installation_status = "installed"
            copilot_impact = "GitHub Copilot CLI is installed, but sign-in is required."
            copilot_action = "Authenticate GitHub Copilot CLI using its approved setup, then Recheck."
        else:
            copilot_installation_status = "unavailable"
            copilot_impact = "GitHub Copilot CLI authentication could not be verified."
            copilot_action = "Check GitHub Copilot CLI availability, then Recheck."
    results.append(_result(
        "external.copilot",
        "GitHub Copilot CLI",
        copilot_status,
        copilot_impact,
        copilot_action,
        copilot_installation_status,
    ))

    if copilot is None:
        datadog_status = "setup_required"
        datadog_impact = "Datadog MCP workflows require GitHub Copilot CLI."
        datadog_action = "Install Copilot CLI and configure Datadog MCP using approved setup, then Recheck."
    else:
        datadog_probe, datadog_configured = _configured_mcp_state(
            copilot, timeout_seconds, "datadog"
        )
        if datadog_probe == "unavailable":
            datadog_status = "unavailable"
            datadog_impact = "Datadog MCP configuration could not be checked."
            datadog_action = "Check GitHub Copilot CLI availability, then Recheck."
            datadog_installation_status = "unavailable"
        elif datadog_probe == "setup_required":
            datadog_status = "setup_required"
            datadog_impact = "Datadog MCP configuration or Copilot authentication needs setup."
            datadog_action = "Authenticate Copilot and configure Datadog MCP using approved setup, then Recheck."
            datadog_installation_status = "setup_required"
        elif datadog_configured:
            datadog_status = "ready"
            datadog_impact = "The Datadog MCP server is configured in GitHub Copilot CLI."
            datadog_action = "No action required."
            datadog_installation_status = "ready"
        else:
            datadog_status = "setup_required"
            datadog_impact = "Datadog MCP is not configured in GitHub Copilot CLI."
            datadog_action = "Configure Datadog MCP using approved setup, then Recheck."
            datadog_installation_status = "setup_required"
    if copilot is None:
        datadog_installation_status = "setup_required"
    results.append(_result(
        "external.datadogMcp",
        "Datadog MCP",
        datadog_status,
        datadog_impact,
        datadog_action,
        datadog_installation_status,
    ))

    m365 = _executable("m365", noc_bin)
    if m365 is None:
        results.append(_result(
            "external.microsoft365",
            "Microsoft 365 CLI",
            "setup_required",
            "Email preview and send are unavailable because Microsoft 365 CLI is not installed.",
            "Install and authenticate Microsoft 365 CLI using its approved setup, then Recheck.",
            "setup_required",
        ))
    else:
        m365_status = _probe_state(m365, ("status",), timeout_seconds)
        if m365_status == "ready":
            results.append(_result(
                "external.microsoft365",
                "Microsoft 365 CLI",
                "ready",
                "The Microsoft 365 CLI status check completed successfully.",
                "No action required.",
                "ready",
            ))
        elif m365_status == "setup_required":
            results.append(_result(
                "external.microsoft365",
                "Microsoft 365 CLI",
                "setup_required",
                "Microsoft 365 CLI is installed, but sign-in is required.",
                "Authenticate Microsoft 365 CLI using its approved setup, then Recheck.",
                "installed",
            ))
        else:
            results.append(_result(
                "external.microsoft365",
                "Microsoft 365 CLI",
                "unavailable",
                "Microsoft 365 CLI authentication or availability could not be verified.",
                "Check Microsoft 365 CLI authentication and availability, then Recheck.",
                "unavailable",
            ))

    noc_tools_missing = False
    noc_tools_unavailable = False
    for command, arguments, expected_output in _NOC_TOOL_PROBES:
        executable = _executable(command, noc_bin, noc_tool=True)
        if executable is None:
            noc_tools_missing = True
        elif not _probe(
            executable,
            arguments,
            timeout_seconds,
            expected_output=expected_output,
        ):
            noc_tools_unavailable = True
    if noc_tools_unavailable:
        results.append(_result(
            "external.nocTools",
            "noc-tools compatibility",
            "unavailable",
            "A required noc-tools command could not complete its compatibility check.",
            "Repair the approved noc-tools installation and run Recheck.",
            "unavailable",
        ))
    elif noc_tools_missing:
        results.append(_result(
            "external.nocTools",
            "noc-tools compatibility",
            "setup_required",
            "Workflows using one or more required noc-tools commands are unavailable.",
            "Restore the compatible noc-tools commands and run Recheck.",
            "setup_required",
        ))
    elif _executable("jq", noc_bin) is None:
        results.append(_result(
            "external.nocTools",
            "noc-tools compatibility",
            "setup_required",
            "noc-tools workflows require jq for local ticket JSON.",
            "Install jq using your distribution's approved process, then Recheck.",
            "setup_required",
        ))
    else:
        results.append(_result(
            "external.nocTools",
            "noc-tools compatibility",
            "ready",
            "Required noc-tools commands passed their bounded compatibility checks.",
            "No action required.",
            "ready",
        ))
    return results
