"""Validation for the immutable bootstrap release policy."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse


MANIFEST_SCHEMA_VERSION = 1
APPLICATION_REPOSITORY = "brentsens/noc-web"
APPLICATION_SIGNER_WORKFLOW = "brentsens/noc-web/.github/workflows/release.yml"
NOC_TOOLS_REPOSITORY = "brentsens/noc-tools"
NOC_TOOLS_SIGNER_WORKFLOW = "brentsens/noc-tools/.github/workflows/noc-release.yml"
TOOL_IDS = frozenset({"atlas", "copilot", "m365", "datadogMcp", "nocTools"})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_TAG = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?$")


class ManifestError(ValueError):
    """A redacted manifest validation error."""


@dataclass(frozen=True)
class ReleaseEntry:
    repository: str
    tag: str
    archive: str
    checksum: str
    sha256: str
    signer_workflow: str

    @property
    def archive_url(self) -> str:
        return f"https://github.com/{self.repository}/releases/download/{self.tag}/{self.archive}"

    @property
    def checksum_url(self) -> str:
        return f"https://github.com/{self.repository}/releases/download/{self.tag}/{self.checksum}"


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
    signer_workflow: str | None = None


@dataclass(frozen=True)
class BootstrapManifest:
    schema_version: int
    application: ReleaseEntry
    target_distribution: str
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


def _release_entry(value: object) -> ReleaseEntry:
    if not isinstance(value, dict) or set(value) != {
        "repository", "tag", "archive", "checksum", "sha256", "signerWorkflow",
    }:
        raise ManifestError("releaseAssets")
    repository = _string(value["repository"], "repository")
    tag = _string(value["tag"], "tag")
    archive = _safe_relative(value["archive"], "archive")
    checksum = _safe_relative(value["checksum"], "checksum")
    signer = _string(value["signerWorkflow"], "signerWorkflow")
    if repository != APPLICATION_REPOSITORY or not _REPOSITORY.fullmatch(repository) or not _TAG.fullmatch(tag):
        raise ManifestError("releaseAssets")
    if not archive.endswith(".tar.gz") or archive == checksum:
        raise ManifestError("releaseAssets")
    if signer != APPLICATION_SIGNER_WORKFLOW:
        raise ManifestError("signerWorkflow")
    return ReleaseEntry(repository, tag, archive, checksum, _sha256(value["sha256"], "sha256"), signer)


def validate_manifest(value: object) -> BootstrapManifest:
    if not isinstance(value, dict):
        raise ManifestError("manifest")
    required = {"schemaVersion", "targetDistribution", "releaseAssets", "brandingAsset", "toolEntries"}
    if set(value) != required or value["schemaVersion"] != MANIFEST_SCHEMA_VERSION:
        raise ManifestError("schemaVersion")
    entries = value["toolEntries"]
    if not isinstance(entries, list):
        raise ManifestError("toolEntries")
    tools: list[ToolEntry] = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "tool", "version", "source", "sha256", "target", "compatibility",
            "requiresConfirmation", "readinessId", "signerWorkflow",
        }:
            raise ManifestError("toolEntries")
        tool = _string(entry["tool"], "tool")
        if tool not in TOOL_IDS or tool in seen or entry["requiresConfirmation"] is not True:
            raise ManifestError("toolEntries")
        seen.add(tool)
        signer = _string(entry["signerWorkflow"], "signerWorkflow")
        if tool == "nocTools" and (
            signer != NOC_TOOLS_SIGNER_WORKFLOW
            or not _source(entry["source"], "source").startswith(
                f"https://github.com/{NOC_TOOLS_REPOSITORY}/releases/download/"
            )
        ):
            raise ManifestError("toolEntries")
        tools.append(ToolEntry(
            tool=tool, version=_string(entry["version"], "version"),
            source=_source(entry["source"], "source"), sha256=_sha256(entry["sha256"], "sha256"),
            target=_safe_relative(entry["target"], "target"),
            compatibility=_string(entry["compatibility"], "compatibility"),
            readiness_id=_string(entry["readinessId"], "readinessId"),
            requires_confirmation=True,
            signer_workflow=signer,
        ))
    return BootstrapManifest(
        schema_version=MANIFEST_SCHEMA_VERSION,
        application=_release_entry(value["releaseAssets"]),
        target_distribution=_string(value["targetDistribution"], "targetDistribution"),
        branding_asset=_safe_relative(value["brandingAsset"], "brandingAsset"),
        tools=tuple(tools),
    )


def load_manifest(path: Path) -> BootstrapManifest:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise ManifestError("manifest") from None
    return validate_manifest(payload)
