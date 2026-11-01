import json
import os
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from backend.config import (
    ConfigurationProfile,
    PROJECT_ROOT,
    RuntimeConfigurationError,
    load_runtime_configuration,
)
from backend.services.jira_cache import read_jira_cache_from


COMMAND_CATALOG = (
    ("tix", ("--help",)),
    ("noc-start", ("--help",)),
    ("noc-status", ("--help",)),
    ("noc-inv", ("--contract-version",)),
    ("copilot", ("--version",)),
    ("noc-handover", ("--help",)),
)

# No network liveness is configured by default. Deployments may deliberately
# replace this immutable catalog with locally safe, documented probes.
LIVENESS_CATALOG: tuple[tuple[str, tuple[str, ...]], ...] = ()


@dataclass(frozen=True)
class ReadinessCheck:
    id: str
    category: str
    status: str
    required: bool
    capability: str
    impact: str
    correctiveAction: str
    sourceId: str | None = None
    ageSeconds: int | None = None

    def serialize(self) -> dict:
        return {
            key: value
            for key, value in asdict(self).items()
            if value is not None
        }


def _check(
    identifier: str,
    category: str,
    status: str,
    capability: str,
    impact: str,
    corrective_action: str,
    *,
    required: bool = True,
    source_id: str | None = None,
    age_seconds: int | None = None,
) -> ReadinessCheck:
    return ReadinessCheck(
        identifier, category, status, required, capability, impact,
        corrective_action, source_id, age_seconds,
    )


def configuration_ready() -> ReadinessCheck:
    return _check(
        "configuration.profile", "configuration", "ready",
        "Approved workstation configuration",
        "Readiness checks use the documented configuration profile.",
        "No action required.",
    )


def profile_configuration_check(profile: ConfigurationProfile) -> ReadinessCheck:
    if (
        not profile.noc_root.is_dir()
        or not profile.noc_bin.is_dir()
        or not profile.probe_directory.is_dir()
    ):
        return _check(
            "configuration.profile", "configuration", "notReady",
            "Approved workstation configuration",
            "The documented workstation configuration cannot be used.",
            "Restore the documented configuration and run readiness again.",
        )
    return configuration_ready()


def configuration_failure(setting: str) -> ReadinessCheck:
    return _check(
        f"configuration.{setting}", "configuration", "notReady",
        "Approved workstation configuration", "Readiness checks were not run.",
        "Correct the documented override and run readiness again.",
    )


def _noc_data_check(profile: ConfigurationProfile, shift_date: str) -> ReadinessCheck:
    records_directory = profile.noc_root / "tickets" / "open"
    try:
        if not profile.noc_root.is_dir() or not records_directory.is_dir():
            raise OSError
        for record_file in records_directory.glob("*.json"):
            record = json.loads(record_file.read_text(encoding="utf-8"))
            if not (
                isinstance(record, dict)
                and isinstance(record.get("id"), str)
                and record["id"]
                and isinstance(record.get("jira"), dict)
                and isinstance(record.get("noc"), dict)
                and isinstance(record.get("metadata"), dict)
            ):
                raise ValueError
    except (OSError, ValueError, json.JSONDecodeError):
        return _check(
            "nocData.records", "nocData", "notReady", "NOC data records",
            "Local NOC records cannot be used for operational work.",
            "Restore compatible local NOC records through the normal workflow.",
        )
    return _check(
        "nocData.records", "nocData", "ready", "NOC data records",
        "Local NOC records are compatible and available.", "No action required.",
    )


def _cache_check(profile: ConfigurationProfile, source_id: str, maximum_age: int) -> ReadinessCheck:
    cache = read_jira_cache_from(profile.noc_root / ".jira-open-tickets.json")
    if cache is None:
        return _check(
            f"cache.{source_id}", "cache", "notReady", "Jira open-ticket cache",
            "Cached ticket data cannot be relied on for operational work.",
            "Restore the approved cache through the normal confirmed workflow.",
            source_id=source_id,
        )
    refreshed_at = cache.get("refreshedAt")
    try:
        refreshed = datetime.fromisoformat(refreshed_at)
        if refreshed.tzinfo is None or refreshed.utcoffset() is None:
            raise ValueError
        age_seconds = max(0, int((datetime.now(timezone.utc) - refreshed).total_seconds()))
    except (TypeError, ValueError):
        return _check(
            f"cache.{source_id}", "cache", "notReady", "Jira open-ticket cache",
            "Cached ticket data cannot be relied on for operational work.",
            "Restore the approved cache through the normal confirmed workflow.",
            source_id=source_id,
        )
    if age_seconds >= maximum_age:
        return _check(
            f"cache.{source_id}", "cache", "notReady", "Jira open-ticket cache",
            "Cached ticket data is too old for operational work.",
            "Restore the approved cache through the normal confirmed workflow.",
            source_id=source_id, age_seconds=age_seconds,
        )
    return _check(
        f"cache.{source_id}", "cache", "ready", "Jira open-ticket cache",
        "Cached ticket data is current for operational work.", "No action required.",
        source_id=source_id, age_seconds=age_seconds,
    )


def _command_checks(profile: ConfigurationProfile) -> list[ReadinessCheck]:
    checks = []
    for command, arguments in COMMAND_CATALOG:
        executable = profile.noc_bin / command
        identifier = f"command.{command}"
        if not executable.is_file() or not os.access(executable, os.X_OK):
            checks.append(_check(
                identifier, "command", "notReady", f"{command} command",
                "A required operational command is unavailable.",
                "Install or restore the documented command and run readiness again.",
                required=command != "copilot",
            ))
            continue
        try:
            expected_output = (
                "noc-inv-contract=1" if command == "noc-inv" else None
            )
            result = subprocess.run(
                [str(executable), *arguments], shell=False, timeout=profile.command_timeout_seconds,
                stdout=subprocess.PIPE if expected_output else subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, check=False, text=True,
            )
            status = (
                "ready"
                if result.returncode == 0
                and (
                    expected_output is None
                    or result.stdout.strip() == expected_output
                )
                else "notReady"
            )
        except (OSError, subprocess.TimeoutExpired):
            status = "notReady"
        checks.append(_check(
            identifier, "command", status, f"{command} command",
            "The required command completed safely." if status == "ready" else
            "A required operational command cannot complete safely.",
            "No action required." if status == "ready" else (
                "Install the compatible noc-inv contract and run readiness again."
                if command == "noc-inv" else
                "Install or restore the documented command and run readiness again."
            ),
            required=command != "copilot",
        ))
    return checks


def _write_probe(directory: Path) -> bool:
    probe_file: Path | None = None
    created = False
    failed = False
    try:
        probe_file = directory / f".readiness-{uuid.uuid4().hex}"
        descriptor = os.open(probe_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(b"ready\n")
            stream.flush()
            os.fsync(stream.fileno())
        probe_file.unlink()
        probe_file = None
        created = False
    except OSError:
        failed = True
    finally:
        if created and probe_file is not None:
            try:
                probe_file.unlink()
            except OSError:
                failed = True
    return not failed


def _write_check(profile: ConfigurationProfile) -> ReadinessCheck:
    if not _write_probe(profile.probe_directory):
        return _check(
            "writeCapability.probe", "writeCapability", "notReady",
            "Approved destination write capability",
            "The approved destination cannot safely accept operational output.",
            "Restore access or capacity for the approved destination and run readiness again.",
        )
    return _check(
        "writeCapability.probe", "writeCapability", "ready",
        "Approved destination write capability",
        "The approved destination accepted non-destructive write evidence.",
        "No action required.",
    )


def _investigation_storage_check(profile: ConfigurationProfile) -> ReadinessCheck:
    if not _write_probe(profile.noc_root):
        return _check(
            "investigationStorage.path", "investigationStorage", "notReady",
            "Investigation record storage",
            "The configured investigation storage cannot safely accept a local record.",
            "Restore access or capacity for the configured NOC storage path.",
        )
    return _check(
        "investigationStorage.path", "investigationStorage", "ready",
        "Investigation record storage",
        "The configured investigation storage accepted a non-destructive write probe.",
        "No action required.",
    )


def _liveness_checks(profile: ConfigurationProfile) -> list[ReadinessCheck]:
    if not LIVENESS_CATALOG:
        return [_check(
            "liveness.external", "liveness", "notConfigured",
            "External dependency response",
            "No documented liveness probe is configured; this does not establish readiness.",
            "Use the individual readiness results.", required=False, source_id="external",
        )]
    checks = []
    for source_id, argv in LIVENESS_CATALOG:
        try:
            response = subprocess.run(
                list(argv), shell=False, timeout=profile.command_timeout_seconds,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            )
            status = "available" if response.returncode == 0 else "unavailable"
        except (OSError, subprocess.TimeoutExpired):
            status = "unavailable"
        checks.append(_check(
            f"liveness.{source_id}", "liveness", status,
            f"{source_id} dependency response",
            "The dependency responded, but this alone does not establish readiness."
            if status == "available" else "The dependency did not respond to its documented probe.",
            "Continue with the individual readiness results." if status == "available" else
            "Restore the documented dependency probe and run readiness again.",
            required=False, source_id=source_id,
        ))
    return checks


def _runtime_result(
    identifier: str,
    category: str,
    capability: str,
    status: str,
    impact: str,
    corrective_action: str,
) -> dict:
    return {
        "id": identifier,
        "category": category,
        "capability": capability,
        "status": status,
        "required": True,
        "impact": impact,
        "correctiveAction": corrective_action,
        "checkedAt": datetime.now(timezone.utc).isoformat(),
    }


def assess_runtime_readiness() -> list[dict]:
    application_ready = sys.version_info >= (3, 10)
    results = [_runtime_result(
        "runtime.application",
        "core",
        "noc-web application runtime",
        "ready" if application_ready else "unavailable",
        "The application is running on a supported Python runtime."
        if application_ready else
        "The application runtime is below the supported Python version.",
        "No action required." if application_ready else
        "Install Python 3.10 or later and run the workstation setup again.",
    )]

    try:
        configuration = load_runtime_configuration()
        if configuration.repository_root != PROJECT_ROOT:
            raise RuntimeConfigurationError("repositoryRoot")
    except RuntimeConfigurationError:
        configuration = None

    results.append(_runtime_result(
        "runtime.configuration",
        "core",
        "Workstation runtime configuration",
        "ready" if configuration else "setup_required",
        "Validated workstation configuration is available."
        if configuration else
        "The managed workstation runtime is not configured or needs repair.",
        "No action required." if configuration else
        "Run the NOC Web workstation setup from its validated checkout.",
    ))

    python_ready = (
        configuration is not None
        and application_ready
        and Path(sys.prefix).resolve() == configuration.virtual_environment
    )
    results.append(_runtime_result(
        "runtime.python",
        "core",
        "Python environment",
        "ready" if python_ready else "setup_required",
        "The application is using its configured virtual environment."
        if python_ready else
        "The configured NOC Web virtual environment is not active.",
        "No action required." if python_ready else
        "Run workstation setup to create or update the configured virtual environment.",
    ))

    if configuration is None:
        service_status = "setup_required"
        service_impact = "The managed user service cannot be verified without valid runtime configuration."
        service_action = "Run workstation setup, then Recheck."
    elif not hasattr(os, "getuid") or os.getuid() == 0:
        service_status = "unavailable"
        service_impact = "The application process is not running as an unprivileged user."
        service_action = "Start NOC Web through the current operator's user service."
    else:
        try:
            service = subprocess.run(
                ["systemctl", "--user", "is-active", "--quiet", "noc-web.service"],
                shell=False,
                timeout=2,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            service_status = "ready" if service.returncode == 0 else "unavailable"
        except (OSError, subprocess.TimeoutExpired):
            service_status = "unavailable"
        service_impact = (
            "The user-owned NOC Web service is active."
            if service_status == "ready" else
            "The user-owned NOC Web service is not active or could not be checked."
        )
        service_action = (
            "No action required." if service_status == "ready" else
            "Start or restart the noc-web user service, then Recheck."
        )
    results.append(_runtime_result(
        "service.noc-web",
        "service",
        "Background service",
        service_status,
        service_impact,
        service_action,
    ))
    return results


def assess_readiness(profile: ConfigurationProfile, shift_date: str) -> dict:
    configuration = profile_configuration_check(profile)
    checks = [_noc_data_check(profile, shift_date)]
    for policy in profile.cache_sources:
        checks.append(_cache_check(profile, policy.source_id, policy.maximum_age_seconds))
    checks.extend(_command_checks(profile))
    checks.append(_write_check(profile))
    checks.append(_investigation_storage_check(profile))
    return {
        "assessedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "shiftDate": shift_date,
        "overallStatus": "ready" if (
            configuration.status == "ready"
            and all(
                check.status == "ready"
                for check in checks
                if check.required
            )
        ) else "notReady",
        "readOnly": True,
        "configuration": configuration.serialize(),
        "checks": [check.serialize() for check in checks],
        "liveness": [check.serialize() for check in _liveness_checks(profile)],
    }
