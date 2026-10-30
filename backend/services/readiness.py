import json
import os
import subprocess
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from backend.config import ConfigurationProfile
from backend.services.jira_cache import read_jira_cache_from


COMMAND_CATALOG = (
    ("tix", ("--help",)),
    ("noc-start", ("--help",)),
    ("noc-status", ("--help",)),
    ("noc-inv", ("--help",)),
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
            ))
            continue
        try:
            result = subprocess.run(
                [str(executable), *arguments], shell=False, timeout=profile.command_timeout_seconds,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            )
            status = "ready" if result.returncode == 0 else "notReady"
        except (OSError, subprocess.TimeoutExpired):
            status = "notReady"
        checks.append(_check(
            identifier, "command", status, f"{command} command",
            "The required command completed safely." if status == "ready" else
            "A required operational command cannot complete safely.",
            "No action required." if status == "ready" else
            "Install or restore the documented command and run readiness again.",
        ))
    return checks


def _write_check(profile: ConfigurationProfile) -> ReadinessCheck:
    probe_file: Path | None = None
    created = False
    failed = False
    try:
        probe_file = profile.probe_directory / f".readiness-{uuid.uuid4().hex}"
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
    if failed:
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


def assess_readiness(profile: ConfigurationProfile, shift_date: str) -> dict:
    configuration = profile_configuration_check(profile)
    checks = [_noc_data_check(profile, shift_date)]
    for policy in profile.cache_sources:
        checks.append(_cache_check(profile, policy.source_id, policy.maximum_age_seconds))
    checks.extend(_command_checks(profile))
    checks.append(_write_check(profile))
    return {
        "assessedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "shiftDate": shift_date,
        "overallStatus": "ready" if (
            configuration.status == "ready"
            and all(check.status == "ready" for check in checks)
        ) else "notReady",
        "readOnly": True,
        "configuration": configuration.serialize(),
        "checks": [check.serialize() for check in checks],
        "liveness": [check.serialize() for check in _liveness_checks(profile)],
    }
