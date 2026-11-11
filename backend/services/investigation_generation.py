import hashlib
import json
import os
import re
import shutil
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urlsplit

from backend.services import investigations
from backend.services.ai_provider import (
    ProviderInvalid,
    ProviderTimeout,
    ProviderUnavailable,
    resolve_provider_runtime,
)
from backend.services.datadog_validation import (
    DatadogValidationError,
    validate_datadog_identifier,
)
from backend.services.investigation_ai import (
    INVESTIGATION_SYSTEM_PROMPT,
    InvestigationAIError,
    build_investigation_envelope,
    validate_ai_output,
)
from backend.services.investigation_evidence import (
    InvestigationEvidenceError,
    build_evidence_package,
    evidence_summary,
)
from backend.services.investigation_preview_store import (
    InvestigationPreviewStore,
    PreviewStoreError,
    get_preview_store,
)
from backend.services.ollama_provider import OllamaModelMissing
from backend.services.local_retry import (
    RetrySnapshotError,
    capture_local_retry,
    get_retry_store,
    resolve_retry_runtime,
)


GenerationStatus = Literal["completed", "failed", "timed_out", "unavailable"]
ValidationStatus = Literal["ready_for_review", "needs_review"]
ReviewState = Literal["unreviewed", "reviewed", "rejected"]


@dataclass(frozen=True)
class InvestigationRequest:
    shift_date: str
    display_title: str
    name: str
    notebook_url: str
    incident_id: str = ""


@dataclass(frozen=True)
class InvestigationGenerationResult:
    generation_status: GenerationStatus
    validation_status: ValidationStatus | None
    review_state: ReviewState
    record: dict | None = None
    error_code: str | None = None


class GenerationError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        field: str | None = None,
        retry_metadata: dict | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.field = field
        self.retry_metadata = retry_metadata


class InvestigationValidationError(ValueError):
    def __init__(self, field: str, code: str, message: str):
        super().__init__(message)
        self.field = field
        self.code = code
        self.message = message


_HEADING_PATTERN = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_METADATA_PATTERN = re.compile(r"^-\s+([^:]+):\s*(.*?)\s*$", re.MULTILINE)
_INVALID_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
_NOTEBOOK_SLUG_CHAR = re.compile(r"(?:[A-Za-z0-9._~!$&'()*+,;=:@-]|%[0-9A-Fa-f]{2})+")
_MAX_DISPLAY_TITLE_LENGTH = 200
_MAX_IDENTIFIER_LENGTH = 80
_MAX_IDENTIFIER_BYTES = 240
_REQUIRED_SECTIONS = (
    "Summary",
    "Confirmed Findings",
    "Current Status",
    "Next Actions",
    "Handover Summary",
)
def _validate_shift(shift_date: str) -> str:
    if not isinstance(shift_date, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", shift_date
    ):
        raise InvestigationValidationError(
            "shiftDate", "invalid_shift", "Selected Shift must use YYYY-MM-DD format."
        )
    try:
        date.fromisoformat(shift_date)
    except ValueError:
        raise InvestigationValidationError(
            "shiftDate", "invalid_shift", "Selected Shift must use YYYY-MM-DD format."
        ) from None
    return shift_date


def normalize_investigation_name(value: str) -> str:
    if not isinstance(value, str):
        raise InvestigationValidationError(
            "name", "required", "Investigation Name is required."
        )
    trimmed = value.strip()
    if (
        not trimmed
        or len(trimmed) > _MAX_DISPLAY_TITLE_LENGTH
        or "/" in trimmed
        or "\\" in trimmed
        or ".." in trimmed
        or any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in trimmed)
    ):
        raise InvestigationValidationError(
            "name",
            "invalid_name",
            "Investigation Name contains unsafe characters or is too long.",
        )
    normalized_characters = []
    for character in unicodedata.normalize("NFKD", trimmed).casefold():
        category = unicodedata.category(character)
        if character.isalnum():
            normalized_characters.append(character)
        elif category.startswith("M"):
            continue
        else:
            normalized_characters.append("-")
    normalized = re.sub(r"-+", "-", "".join(normalized_characters)).strip("-")
    if (
        not normalized
        or len(normalized) > _MAX_IDENTIFIER_LENGTH
        or len(normalized.encode("utf-8")) > _MAX_IDENTIFIER_BYTES
        or not normalized[0].isalnum()
        or not normalized[-1].isalnum()
        or any(not (character.isalnum() or character == "-") for character in normalized)
    ):
        raise InvestigationValidationError(
            "name",
            "invalid_name",
            "Investigation Name does not produce a safe local identifier.",
        )
    return normalized


def validate_display_title(value: str) -> str:
    if not isinstance(value, str):
        raise InvestigationValidationError(
            "displayTitle", "invalid_display_title", "Datadog Incident Title is invalid."
        )
    trimmed = value.strip()
    if (
        not trimmed
        or len(trimmed) > _MAX_DISPLAY_TITLE_LENGTH
        or any(unicodedata.category(character) in {"Cc", "Cf", "Cs"} for character in trimmed)
    ):
        raise InvestigationValidationError(
            "displayTitle",
            "invalid_display_title",
            "Datadog Incident Title is invalid.",
        )
    return trimmed


def slugify_incident_title(value: str) -> str:
    """Create a deterministic filesystem-safe identifier from an incident title."""
    title = value if isinstance(value, str) else ""
    normalized = unicodedata.normalize("NFKD", title).casefold()
    characters = []
    for character in normalized:
        category = unicodedata.category(character)
        if character.isalnum():
            characters.append(character)
        elif category.startswith("M"):
            continue
        else:
            characters.append("-")
    slug = re.sub(r"-+", "-", "".join(characters)).strip("-")
    if not slug:
        stripped = title.strip()
        if not stripped:
            return "datadog-incident"
        digest = hashlib.sha256(stripped.encode("utf-8")).hexdigest()[:8]
        return f"datadog-incident-{digest}"
    if len(slug) > _MAX_IDENTIFIER_LENGTH or len(slug.encode("utf-8")) > _MAX_IDENTIFIER_BYTES:
        digest = hashlib.sha256(title.strip().encode("utf-8")).hexdigest()[:8]
        prefix = slug[: _MAX_IDENTIFIER_LENGTH - 9].rstrip("-")
        slug = f"{prefix}-{digest}" if prefix else f"datadog-incident-{digest}"
        if len(slug.encode("utf-8")) > _MAX_IDENTIFIER_BYTES:
            slug = f"datadog-incident-{digest}"
    return slug


def validate_notebook_url(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise InvestigationValidationError(
            "notebookUrl", "required", "FINAL Datadog Notebook URL is required."
        )
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise InvestigationValidationError(
            "notebookUrl",
            "invalid_url",
            "FINAL Datadog Notebook URL contains control characters.",
        )
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise InvestigationValidationError(
            "notebookUrl", "invalid_url", "FINAL Datadog Notebook URL is invalid."
        ) from None
    path_segments: list[str] = []
    path_is_safe = False
    if not _INVALID_PERCENT_ESCAPE.search(parsed.path):
        try:
            decoded_path = unquote(parsed.path, errors="strict")
        except UnicodeDecodeError:
            decoded_path = ""
        if decoded_path:
            path_segments = decoded_path.split("/")
            path_is_safe = (
                len(path_segments) in {3, 4}
                and path_segments[0] == ""
                and path_segments[1] == "notebook"
                and path_segments[2].isascii()
                and path_segments[2].isdecimal()
            )
            if len(path_segments) == 4:
                slug = path_segments[3]
                path_is_safe = (
                    path_is_safe
                    and bool(slug)
                    and slug not in {".", ".."}
                    and bool(
                        _NOTEBOOK_SLUG_CHAR.fullmatch(
                            parsed.path.rsplit("/", 1)[-1]
                        )
                    )
                )
            if any(unicodedata.category(character) == "Cc" for character in decoded_path):
                path_is_safe = False

            traversal_path = decoded_path
            for _ in range(3):
                traversal_segments = traversal_path.split("/")
                if (
                    len(traversal_segments) not in {3, 4}
                    or traversal_segments[:2] != ["", "notebook"]
                    or not traversal_segments[2].isascii()
                    or not traversal_segments[2].isdecimal()
                    or any(segment in {".", ".."} for segment in traversal_segments)
                ):
                    path_is_safe = False
                    break
                decoded_again = unquote(traversal_path)
                if decoded_again == traversal_path:
                    break
                traversal_path = decoded_again
    if (
        parsed.scheme != "https"
        or parsed.hostname != "app.datadoghq.com"
        or parsed.netloc != "app.datadoghq.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not path_is_safe
    ):
        raise InvestigationValidationError(
            "notebookUrl",
            "invalid_url",
            "Use a FINAL Datadog Notebook URL from app.datadoghq.com with a numeric Notebook ID.",
        )
    return value


def validate_target(
    shift_date: str,
    name: str,
    notebook_url: str,
) -> InvestigationRequest:
    validated_shift = _validate_shift(shift_date)
    if not isinstance(name, str) or not name.strip():
        raise InvestigationValidationError(
            "name", "required", "Investigation Name is required."
        )
    display_title = name.strip()
    normalized_name = normalize_investigation_name(display_title)
    return InvestigationRequest(
        shift_date=validated_shift,
        display_title=display_title,
        name=normalized_name,
        notebook_url=validate_notebook_url(notebook_url),
    )


def validate_preview_request(
    shift_date: str,
    name: str | None,
    notebook_url: str,
    incident_id: str,
    display_title: str | None = None,
) -> InvestigationRequest:
    validated_shift = _validate_shift(shift_date)
    try:
        validated_incident = validate_datadog_identifier(
            incident_id,
            rule="invalid_incident_id",
        )
    except DatadogValidationError:
        raise InvestigationValidationError(
            "incidentId",
            "invalid_incident_id",
            "A valid current Datadog Incident ID is required.",
        ) from None
    if name is not None:
        normalized_name = normalize_investigation_name(name)
        validated_display_title = validate_display_title(
            display_title if display_title is not None and display_title.strip()
            else name
        )
    elif display_title is not None and display_title.strip():
        validated_display_title = validate_display_title(display_title)
        normalized_name = slugify_incident_title(validated_display_title)
    else:
        raise InvestigationValidationError(
            "displayTitle",
            "invalid_display_title",
            "A Datadog Incident Title or Investigation Name is required.",
        )
    return InvestigationRequest(
        shift_date=validated_shift,
        display_title=validated_display_title,
        name=normalized_name,
        notebook_url=validate_notebook_url(notebook_url),
        incident_id=validated_incident,
    )


def validate_request(
    shift_date: str,
    name: str,
    notebook_url: str,
    incident_id: str,
) -> InvestigationRequest:
    return validate_preview_request(
        shift_date,
        name,
        notebook_url,
        incident_id,
    )


def _target_directory(request: InvestigationRequest) -> Path:
    root = investigations.get_noc_root().resolve()
    target = root / request.shift_date / "investigations" / request.name
    try:
        target.parent.resolve(strict=False).relative_to(root)
    except ValueError:
        raise GenerationError(
            503, "storage-unavailable", "Investigation storage is unavailable."
        ) from None
    current = root
    for part in (request.shift_date, "investigations", request.name):
        current = current / part
        if current.is_symlink():
            raise GenerationError(
                503, "storage-unavailable", "Investigation storage is unavailable."
            )
    return target


def _provider_metadata(runtime) -> dict:
    readiness = runtime.readiness if isinstance(runtime.readiness, dict) else {}
    return {
        "configuredProvider": runtime.identifier,
        "label": readiness.get("label"),
        "model": readiness.get("model"),
        "readiness": readiness.get("readiness"),
    }


def _require_provider(runtime) -> None:
    readiness = runtime.readiness if runtime is not None and isinstance(runtime.readiness, dict) else {}
    if (
        runtime is None
        or runtime.provider is None
        or readiness.get("readiness") == "notConfigured"
    ):
        raise GenerationError(
            503,
            "provider-not-configured",
            "No AI provider is configured for investigation generation.",
        )
    if readiness.get("readiness") != "ready":
        raise GenerationError(
            503,
            "provider-not-ready",
            "The configured AI provider is not ready.",
        )


def _resolve_provider():
    return resolve_provider_runtime(system_prompt=INVESTIGATION_SYSTEM_PROMPT)


def _retry_payload(request, package, envelope):
    return {
        "request": {
            "shift_date": request.shift_date,
            "display_title": request.display_title,
            "name": request.name,
            "notebook_url": request.notebook_url,
            "incident_id": request.incident_id,
        },
        "package": package,
        "envelope": envelope,
    }


def _capture_retry(request, package, envelope):
    return capture_local_retry(
        workflow="investigation",
        shift_date=request.shift_date,
        identity=request.name,
        payload=_retry_payload(request, package, envelope),
    )


def _provider_error(error, request, package, envelope):
    retry = _capture_retry(request, package, envelope)
    if isinstance(error, ProviderTimeout):
        return GenerationError(
            504,
            "provider-timeout",
            "The AI provider timed out.",
            retry_metadata=retry,
        )
    if isinstance(error, ProviderInvalid):
        return GenerationError(
            502,
            "provider-invalid-response",
            "The AI provider returned an invalid response.",
            retry_metadata=retry,
        )
    if isinstance(error, OllamaModelMissing):
        return GenerationError(
            503,
            "ollama-model-missing",
            "The configured local model is unavailable.",
            retry_metadata=retry,
        )
    if isinstance(error, ProviderUnavailable):
        return GenerationError(
            503,
            "provider-unavailable",
            "The AI provider is unavailable.",
            retry_metadata=retry,
        )
    return GenerationError(
        502,
        "provider-invalid-response",
        "The AI provider returned an invalid response.",
        retry_metadata=retry,
    )


def _run_provider(runtime, envelope, *, request=None, package=None):
    try:
        return runtime.provider(envelope)
    except (ProviderTimeout, ProviderInvalid, ProviderUnavailable) as error:
        if request is not None and package is not None:
            raise _provider_error(error, request, package, envelope) from None
        if isinstance(error, OllamaModelMissing):
            raise GenerationError(
                503,
                "ollama-model-missing",
                "The configured local model is unavailable.",
            ) from None
        if isinstance(error, ProviderTimeout):
            raise GenerationError(504, "provider-timeout", "The AI provider timed out.") from None
        if isinstance(error, ProviderInvalid):
            raise GenerationError(
                502, "provider-invalid-response", "The AI provider returned an invalid response."
            ) from None
        raise GenerationError(
            503, "provider-unavailable", "The AI provider is unavailable."
        ) from None
    except (OSError, TimeoutError):
        if request is not None and package is not None:
            raise _provider_error(ProviderUnavailable("down"), request, package, envelope) from None
        raise GenerationError(
            503, "provider-unavailable", "The AI provider is unavailable."
        ) from None
    except Exception:
        if request is not None and package is not None:
            raise _provider_error(ProviderInvalid("bad"), request, package, envelope) from None
        raise GenerationError(
            502, "provider-invalid-response", "The AI provider returned an invalid response."
        ) from None


def _evidence_error(error: InvestigationEvidenceError) -> GenerationError:
    status_code = 504 if error.code == "evidence-timeout" else 503
    if error.code in {"evidence-invalid", "evidence-too-large", "incident-not-current", "evidence-credential-detected"}:
        status_code = 422
    return GenerationError(status_code, error.code, error.message)


def _preview_error(error: PreviewStoreError) -> GenerationError:
    return GenerationError(409, error.code, error.message)


def _store_for(preview_store: InvestigationPreviewStore | None) -> InvestigationPreviewStore:
    return preview_store or get_preview_store()


def preview_investigation(
    shift_date: str,
    name: str | None,
    notebook_url: str,
    incident_id: str,
    *,
    display_title: str | None = None,
    evidence_loader=None,
    provider_runtime=None,
    preview_store: InvestigationPreviewStore | None = None,
) -> dict:
    request = validate_preview_request(
        shift_date,
        name,
        notebook_url,
        incident_id,
        display_title,
    )
    target = _target_directory(request)
    if target.exists():
        raise GenerationError(
            409,
            "investigation-conflict",
            "An investigation with this normalized name already exists.",
            field="name",
        )
    runtime = provider_runtime or _resolve_provider()
    _require_provider(runtime)
    try:
        package = build_evidence_package(
            request.incident_id,
            evidence_loader=evidence_loader,
        )
    except InvestigationEvidenceError as error:
        raise _evidence_error(error) from None
    snapshot = _store_for(preview_store).put({
        "request": {
            "shiftDate": request.shift_date,
            "displayTitle": request.display_title,
            "name": request.name,
            "notebookUrl": request.notebook_url,
            "incidentId": request.incident_id,
        },
        "package": package,
        "packageDigest": package["digest"],
        "provider": runtime.identifier,
        "model": _provider_metadata(runtime).get("model"),
    })
    return {
        "previewId": snapshot["previewId"],
        "expiresAt": snapshot["expiresAtIso"],
        "shiftDate": request.shift_date,
        "displayTitle": request.display_title,
        "normalizedName": request.name,
        "notebookUrl": request.notebook_url,
        "incident": {
            "id": request.incident_id,
            "title": package["incident"].get("title"),
            "state": package["incident"].get("state"),
            "severity": package["incident"].get("severity"),
        },
        "evidence": evidence_summary(package),
        "provider": _provider_metadata(runtime),
        "generation": "Feature 015 read-only Datadog evidence -> configured AI provider",
        "datadogReadOnly": True,
        "requiresOperatorReview": True,
    }


def _render_markdown(
    request: InvestigationRequest,
    package: dict,
    output: dict[str, list[str]],
) -> str:
    status = "PARTIAL" if package.get("availability") == "partial" else "COMPLETE"
    references = ", ".join(sorted(package.get("references", {})))
    lines = [
        f"# Investigation: {request.display_title}",
        f"- Display Title: {request.display_title}",
        f"- Investigation Name: {request.name}",
        f"- Shift Date: {request.shift_date}",
        f"- FINAL Datadog Notebook: {request.notebook_url}",
        "- Evidence Provenance: ai-evidence",
        f"- Evidence Status: {status}",
        f"- Evidence References: {references}",
        "",
    ]
    for section in (
        "Summary",
        "Confirmed Findings",
        "Current Status",
        "Next Actions",
        "Handover Summary",
    ):
        key = {
            "Summary": "summary",
            "Confirmed Findings": "confirmedFindings",
            "Current Status": "currentStatus",
            "Next Actions": "nextActions",
            "Handover Summary": "handoverSummary",
        }[section]
        lines.append(f"## {section}")
        for item in output[key]:
            lines.append(f"- {item}")
        lines.append("")
    if status == "PARTIAL":
        lines.append("## Evidence Availability")
        unavailable_items = [
            item
            for item in package.get("unavailable", [])
            if isinstance(item, dict)
        ]
        if not unavailable_items:
            lines.append(
                "- Partial evidence: some referenced evidence was unavailable."
            )
        for item in unavailable_items:
            lines.append(
                f"- Partial evidence: {item.get('id')} unavailable "
                f"({item.get('error')})."
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _validate_generated_record(
    content: str,
    request: InvestigationRequest,
) -> tuple[str, list[str]]:
    metadata = {
        key.strip().casefold(): value.strip()
        for key, value in _METADATA_PATTERN.findall(content)
    }
    errors = []
    title_match = re.search(r"^# Investigation:\s*(.+?)\s*$", content, re.MULTILINE)
    if not title_match or not title_match.group(1).strip():
        errors.append("title")
    if metadata.get("display title") != request.display_title:
        errors.append("display_title")
    if metadata.get("investigation name") != request.name:
        errors.append("name")
    if metadata.get("shift date") != request.shift_date:
        errors.append("shift")
    if metadata.get("final datadog notebook") != request.notebook_url:
        errors.append("notebook")
    provenance = metadata.get("evidence provenance", "").casefold()
    if provenance in {"noc-inv", "ai-evidence", "copilot-mcp"}:
        normalized_provenance = provenance
    elif provenance == "copilot mcp":
        normalized_provenance = "copilot-mcp"
    else:
        normalized_provenance = ""
        errors.append("provenance")
    for heading in _REQUIRED_SECTIONS:
        if _is_placeholder(_section_content(content, heading)):
            errors.append(f"section:{heading}")
    return normalized_provenance, errors


def _section_content(content: str, heading: str) -> str:
    matches = list(_HEADING_PATTERN.finditer(content))
    for index, match in enumerate(matches):
        if match.group(1).strip().casefold() == heading.casefold():
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            return content[match.end():end].strip()
    return ""


def _is_placeholder(value: str) -> bool:
    normalized = re.sub(r"[*`_\s]+", " ", value).strip().casefold()
    return not normalized or normalized in {
        "tbd",
        "todo",
        "n/a",
        "na",
        "none",
        "pending",
        "to be determined",
        "no data available",
        "placeholder",
    }


def _publish(
    request: InvestigationRequest,
    package: dict,
    content: str,
    runtime,
) -> None:
    target = _target_directory(request)
    if target.exists():
        raise GenerationError(
            409,
            "investigation-conflict",
            "An investigation with this normalized name already exists.",
            field="name",
        )
    profile_root = investigations.get_noc_root()
    try:
        profile_root.mkdir(parents=True, exist_ok=True)
        staging_context = tempfile.TemporaryDirectory(
            prefix=".investigation-generation-",
            dir=profile_root,
        )
    except OSError:
        raise GenerationError(
            503, "storage-unavailable", "Investigation storage is unavailable."
        ) from None
    with staging_context as temporary_directory:
        staging = Path(temporary_directory)
        published = staging / "published"
        published.mkdir(mode=0o700)
        provider = _provider_metadata(runtime)
        generation_status = {
            "generationStatus": "completed",
            "validationStatus": "ready_for_review",
            "validationIssues": [],
            "shiftDate": request.shift_date,
            "name": request.name,
            "displayTitle": request.display_title,
            "notebookUrl": request.notebook_url,
            "incidentId": request.incident_id,
            "provenance": "ai-evidence",
            "evidenceStatus": package.get("availability"),
            "provider": provider.get("configuredProvider"),
            "model": provider.get("model"),
        }
        evidence_provenance = {
            "provenance": "ai-evidence",
            "availability": package.get("availability"),
            "incidentId": request.incident_id,
            "packageDigest": package.get("digest"),
            "provider": {
                "configuredProvider": provider.get("configuredProvider"),
                "model": provider.get("model"),
            },
            "references": package.get("references", {}),
            "unavailable": package.get("unavailable", []),
        }
        (published / "investigation.md").write_text(content, encoding="utf-8")
        (published / "generation-status.json").write_text(
            json.dumps(generation_status, indent=2) + "\n",
            encoding="utf-8",
        )
        (published / "evidence-provenance.json").write_text(
            json.dumps(evidence_provenance, indent=2) + "\n",
            encoding="utf-8",
        )
        (published / "reviewed-context.json").write_text(
            json.dumps({
                "reviewState": "unreviewed",
                "lifecycleStatus": "ready_for_review",
                "finding": "",
                "state": "",
                "lastLifecycleChangedAt": None,
                "lastLifecycleChangedShiftDate": None,
            }, indent=2) + "\n",
            encoding="utf-8",
        )
        target_parent = target.parent
        try:
            target_parent.mkdir(parents=True, exist_ok=True)
            target_parent.resolve(strict=True).relative_to(profile_root.resolve())
            target.mkdir(mode=0o700)
        except FileExistsError:
            raise GenerationError(
                409,
                "investigation-conflict",
                "An investigation with this normalized name already exists.",
                field="name",
            ) from None
        except (OSError, ValueError):
            raise GenerationError(
                500, "storage-failed", "The investigation record could not be stored."
            ) from None
        try:
            for filename in (
                "generation-status.json",
                "investigation.md",
                "evidence-provenance.json",
                "reviewed-context.json",
            ):
                os.replace(published / filename, target / filename)
        except OSError:
            shutil.rmtree(target, ignore_errors=True)
            raise GenerationError(
                500, "storage-failed", "The investigation record could not be stored."
            ) from None


def create_investigation(
    shift_date: str,
    name: str,
    notebook_url: str,
    preview_id: str,
    confirmed: bool,
    *,
    preview_store: InvestigationPreviewStore | None = None,
    evidence_loader=None,
    provider_runtime=None,
) -> InvestigationGenerationResult:
    if confirmed is not True:
        raise GenerationError(
            422,
            "confirmation-required",
            "Explicit confirmation is required before AI generation.",
        )
    target = validate_target(shift_date, name, notebook_url)
    if _target_directory(target).exists():
        raise GenerationError(
            409,
            "investigation-conflict",
            "An investigation with this normalized name already exists.",
            field="name",
        )
    store = _store_for(preview_store)
    try:
        snapshot = store.consume(preview_id)
    except PreviewStoreError as error:
        raise _preview_error(error) from None
    snapshot_request = snapshot.get("request")
    if not isinstance(snapshot_request, dict):
        raise GenerationError(409, "preview-mismatch", "The investigation preview is invalid.")
    if (
        snapshot_request.get("shiftDate") != target.shift_date
        or snapshot_request.get("name") != target.name
        or snapshot_request.get("notebookUrl") != target.notebook_url
    ):
        raise GenerationError(
            409,
            "preview-mismatch",
            "The investigation request does not match the preview.",
        )
    snapshot_display_title = snapshot_request.get("displayTitle")
    try:
        display_title = validate_display_title(snapshot_display_title)
    except InvestigationValidationError:
        raise GenerationError(
            409,
            "preview-mismatch",
            "The investigation preview is invalid.",
        ) from None
    request = InvestigationRequest(
        shift_date=target.shift_date,
        display_title=display_title,
        name=target.name,
        notebook_url=target.notebook_url,
        incident_id=str(snapshot_request.get("incidentId", "")),
    )
    runtime = provider_runtime or _resolve_provider()
    _require_provider(runtime)
    provider = _provider_metadata(runtime)
    if (
        snapshot.get("provider") != runtime.identifier
        or snapshot.get("model") != provider.get("model")
    ):
        raise GenerationError(
            409,
            "preview-stale",
            "The configured AI provider changed; preview the investigation again.",
        )
    package = snapshot.get("package")
    if not isinstance(package, dict):
        raise GenerationError(409, "preview-stale", "The investigation preview is invalid.")
    try:
        refreshed = build_evidence_package(
            request.incident_id,
            evidence_loader=evidence_loader,
        )
    except InvestigationEvidenceError as error:
        raise _evidence_error(error) from None
    if refreshed.get("digest") != snapshot.get("packageDigest"):
        raise GenerationError(
            409,
            "preview-stale",
            "Datadog evidence changed; preview the investigation again.",
        )
    envelope = build_investigation_envelope(package, {
        "displayTitle": request.display_title,
        "name": request.name,
        "shiftDate": request.shift_date,
        "notebookUrl": request.notebook_url,
    })
    raw_output = _run_provider(
        runtime,
        envelope,
        request=request,
        package=package,
    )
    try:
        output = validate_ai_output(raw_output, package)
    except InvestigationAIError as error:
        raise GenerationError(
            422,
            error.code,
            error.message,
            retry_metadata=_capture_retry(request, package, envelope),
        ) from None
    content = _render_markdown(request, package, output)
    _, validation_errors = _validate_generated_record(content, request)
    if validation_errors:
        raise GenerationError(
            500,
            "generated-output-invalid",
            "The generated investigation record did not pass validation.",
            retry_metadata=_capture_retry(request, package, envelope),
        )
    _publish(request, package, content, runtime)
    record = investigations.get_investigation(request.shift_date, request.name)
    if record is None:
        raise GenerationError(
            500,
            "record-unavailable",
            "The created investigation record is unavailable.",
        )
    return InvestigationGenerationResult(
        generation_status="completed",
        validation_status="ready_for_review",
        review_state="unreviewed",
        record=record,
        error_code=None,
    )


def retry_investigation_generation(
    shift_date: str,
    retry_token: str,
    *,
    store=None,
) -> InvestigationGenerationResult:
    try:
        snapshot = (store or get_retry_store()).consume(
            retry_token,
            workflow="investigation",
            shift_date=shift_date,
        )
    except RetrySnapshotError as error:
        raise GenerationError(
            error.status_code,
            error.code,
            error.message,
        ) from None
    payload = snapshot.get("payload")
    request_data = payload.get("request") if isinstance(payload, dict) else None
    package = payload.get("package") if isinstance(payload, dict) else None
    envelope = payload.get("envelope") if isinstance(payload, dict) else None
    if (
        not isinstance(request_data, dict)
        or not isinstance(package, dict)
        or not isinstance(envelope, dict)
    ):
        raise GenerationError(
            409,
            "retry-snapshot-unavailable",
            "The exact failed-request snapshot is unavailable.",
        )
    try:
        request = InvestigationRequest(**request_data)
    except TypeError:
        raise GenerationError(
            409,
            "retry-snapshot-unavailable",
            "The exact failed-request snapshot is unavailable.",
        ) from None
    if request.shift_date != shift_date:
        raise GenerationError(
            409,
            "retry-snapshot-unavailable",
            "The exact failed-request snapshot is unavailable.",
        )
    try:
        runtime = resolve_retry_runtime()
    except RetrySnapshotError as error:
        raise GenerationError(
            error.status_code,
            error.code,
            error.message,
        ) from None
    _require_provider(runtime)
    raw_output = _run_provider(runtime, envelope)
    try:
        output = validate_ai_output(raw_output, package)
    except InvestigationAIError as error:
        raise GenerationError(422, error.code, error.message) from None
    content = _render_markdown(request, package, output)
    _, validation_errors = _validate_generated_record(content, request)
    if validation_errors:
        raise GenerationError(
            500,
            "generated-output-invalid",
            "The generated investigation record did not pass validation.",
        )
    _publish(request, package, content, runtime)
    record = investigations.get_investigation(request.shift_date, request.name)
    if record is None:
        raise GenerationError(
            500,
            "record-unavailable",
            "The created investigation record is unavailable.",
        )
    return InvestigationGenerationResult(
        generation_status="completed",
        validation_status="ready_for_review",
        review_state="unreviewed",
        record=record,
        error_code=None,
    )
