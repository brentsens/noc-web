"""Validation for the signed-release bootstrap policy."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse


MANIFEST_SCHEMA_VERSION = 1
TOOL_IDS = frozenset({"atlas", "copilot", "m365", "datadogMcp", "nocTools"})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ManifestError(ValueError):
    """A redacted manifest validation error."""


@dataclass(frozen=True)
class ToolEntry:
    tool: str
    version: str
    source: str
    sha256: str
    target: str
    compatibility: str
    readiness_id: str
    requires_confirmation: bool


@dataclass(frozen=True)
class BootstrapManifest:
    schema_version: int
    application_repository: str
    release_public_key: str
    target_distribution: str
    archive_name: str
    checksums_name: str
    signature_name: str
    branding_asset: str
    tools: tuple[ToolEntry, ...]

    def tool(self, identifier: str) -> ToolEntry | None:
        return next((entry for entry in self.tools if entry.tool == identifier), None)


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ManifestError(field)
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ManifestError(field)
    return value


def _safe_relative(value: object, field: str) -> str:
    text = _string(value, field)
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts or path == PurePosixPath("."):
        raise ManifestError(field)
    return text


def _source(value: object, field: str) -> str:
    text = _string(value, field)
    parsed = urlparse(text)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ManifestError(field)
    return text


def _sha256(value: object, field: str) -> str:
    text = _string(value, field).lower()
    if not _SHA256.fullmatch(text):
        raise ManifestError(field)
    return text


def validate_manifest(value: object) -> BootstrapManifest:
    if not isinstance(value, dict):
        raise ManifestError("manifest")
    required = {
        "schemaVersion",
        "applicationRepository",
        "releasePublicKey",
        "targetDistribution",
        "releaseAssets",
        "brandingAsset",
        "toolEntries",
    }
    if set(value) != required or value["schemaVersion"] != MANIFEST_SCHEMA_VERSION:
        raise ManifestError("schemaVersion")
    repository = _string(value["applicationRepository"], "applicationRepository")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ManifestError("applicationRepository")
    assets = value["releaseAssets"]
    if not isinstance(assets, dict) or set(assets) != {"archive", "checksums", "signature"}:
        raise ManifestError("releaseAssets")
    entries = value["toolEntries"]
    if not isinstance(entries, list):
        raise ManifestError("toolEntries")
    tools: list[ToolEntry] = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "tool", "version", "source", "sha256", "target", "compatibility",
            "requiresConfirmation", "readinessId",
        }:
            raise ManifestError("toolEntries")
        tool = _string(entry["tool"], "tool")
        if tool not in TOOL_IDS or tool in seen or entry["requiresConfirmation"] is not True:
            raise ManifestError("toolEntries")
        seen.add(tool)
        tools.append(ToolEntry(
            tool=tool,
            version=_string(entry["version"], "version"),
            source=_source(entry["source"], "source"),
            sha256=_sha256(entry["sha256"], "sha256"),
            target=_safe_relative(entry["target"], "target"),
            compatibility=_string(entry["compatibility"], "compatibility"),
            readiness_id=_string(entry["readinessId"], "readinessId"),
            requires_confirmation=True,
        ))
    return BootstrapManifest(
        schema_version=MANIFEST_SCHEMA_VERSION,
        application_repository=repository,
        release_public_key=_safe_relative(value["releasePublicKey"], "releasePublicKey"),
        target_distribution=_string(value["targetDistribution"], "targetDistribution"),
        archive_name=_safe_relative(assets["archive"], "archive"),
        checksums_name=_safe_relative(assets["checksums"], "checksums"),
        signature_name=_safe_relative(assets["signature"], "signature"),
        branding_asset=_safe_relative(value["brandingAsset"], "brandingAsset"),
        tools=tuple(tools),
    )


def load_manifest(path: Path) -> BootstrapManifest:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise ManifestError("manifest") from None
    return validate_manifest(payload)
