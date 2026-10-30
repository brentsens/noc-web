import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urlsplit

from backend.config import ConfigurationError, resolve_readiness_profile
from backend.services import investigations


GenerationStatus = Literal["completed", "failed", "timed_out", "unavailable"]
ValidationStatus = Literal["ready_for_review", "needs_review"]
ReviewState = Literal["unreviewed", "reviewed", "rejected"]


@dataclass(frozen=True)
class InvestigationRequest:
    shift_date: str
    display_title: str
    name: str
    notebook_url: str


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
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.field = field


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
_MAX_RECORD_BYTES = 1_000_000
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
    if not isinstance(shift_date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", shift_date):
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
            "name", "invalid_name", "Investigation Name contains unsafe characters or is too long."
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
            "name", "invalid_name", "Investigation Name does not produce a safe local identifier."
        )
    return normalized


def validate_notebook_url(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise InvestigationValidationError(
            "notebookUrl", "required", "FINAL Datadog Notebook URL is required."
        )
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise InvestigationValidationError(
            "notebookUrl", "invalid_url", "FINAL Datadog Notebook URL contains control characters."
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
                    and bool(_NOTEBOOK_SLUG_CHAR.fullmatch(
                        parsed.path.rsplit("/", 1)[-1]
                    ))
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


def validate_request(shift_date: str, name: str, notebook_url: str) -> InvestigationRequest:
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


def _target_directory(request: InvestigationRequest) -> Path:
    root = investigations.get_noc_root().resolve()
    target = root / request.shift_date / "investigations" / request.name
    try:
        target.parent.resolve(strict=False).relative_to(root)
    except ValueError:
        raise GenerationError(503, "storage-unavailable", "Investigation storage is unavailable.") from None
    current = root
    for part in (request.shift_date, "investigations", request.name):
        current = current / part
        if current.is_symlink():
            raise GenerationError(503, "storage-unavailable", "Investigation storage is unavailable.")
    return target


def preview_investigation(shift_date: str, name: str, notebook_url: str) -> dict:
    request = validate_request(shift_date, name, notebook_url)
    target = _target_directory(request)
    if target.exists():
        raise GenerationError(
            409,
            "investigation-conflict",
            "An investigation with this normalized name already exists.",
            field="name",
        )
    return {
        "shiftDate": request.shift_date,
        "displayTitle": request.display_title,
        "normalizedName": request.name,
        "notebookUrl": request.notebook_url,
        "target": f"{request.shift_date}/{request.name}",
        "generation": "noc-inv -> GitHub Copilot CLI -> Datadog MCP",
        "datadogReadOnly": True,
        "requiresOperatorReview": True,
    }


def _read_output(path: Path) -> tuple[str | None, str]:
    try:
        file_stat = path.lstat()
        if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_size > _MAX_RECORD_BYTES:
            return None, "unsafe-output"
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None, "missing-output"
    if "\x00" in content or any(
        ord(char) < 32 and char not in "\n\r\t" for char in content
    ):
        return None, "unsafe-output"
    return content, ""


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
        "tbd", "todo", "n/a", "na", "none", "pending",
        "to be determined", "no data available", "placeholder",
    }


def _validate_generated_record(content: str, request: InvestigationRequest) -> tuple[str, list[str]]:
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
    if provenance == "noc-inv":
        normalized_provenance = "noc-inv"
    elif provenance == "copilot mcp":
        normalized_provenance = "copilot-mcp"
    else:
        normalized_provenance = ""
        errors.append("provenance")
    for heading in _REQUIRED_SECTIONS:
        if _is_placeholder(_section_content(content, heading)):
            errors.append(f"section:{heading}")
    return normalized_provenance, errors


def _include_display_title(content: str, display_title: str) -> str:
    content = re.sub(
        r"(?m)^-\s+Display Title:.*(?:\n|$)",
        "",
        content,
    )
    title_match = re.search(r"^# Investigation:.*$", content, re.MULTILINE)
    if not title_match:
        return content
    end = title_match.end()
    return f"{content[:end]}\n- Display Title: {display_title}{content[end:]}"


def _profile():
    try:
        return resolve_readiness_profile()
    except ConfigurationError:
        raise GenerationError(503, "configuration-unavailable", "Investigation generation is unavailable.") from None


def create_investigation(
    shift_date: str,
    name: str,
    notebook_url: str,
) -> InvestigationGenerationResult:
    request = validate_request(shift_date, name, notebook_url)
    profile = _profile()
    target = _target_directory(request)
    if target.exists():
        raise GenerationError(
            409,
            "investigation-conflict",
            "An investigation with this normalized name already exists.",
            field="name",
        )
    executable = profile.noc_bin / "noc-inv"
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise GenerationError(503, "noc-inv-unavailable", "The investigation generator is unavailable.")
    copilot = profile.noc_bin / "copilot"
    if not copilot.is_file() or not os.access(copilot, os.X_OK):
        raise GenerationError(503, "copilot-unavailable", "GitHub Copilot CLI is unavailable.")
    environment = os.environ.copy()
    environment["PATH"] = os.pathsep.join(
        (str(profile.noc_bin), environment.get("PATH", ""))
    )
    try:
        contract = subprocess.run(
            [str(executable), "--contract-version"],
            shell=False,
            cwd=profile.noc_root,
            env=environment,
            timeout=min(profile.command_timeout_seconds, 10),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise GenerationError(
            503, "noc-inv-incompatible", "The investigation generator is incompatible."
        ) from None
    except OSError:
        raise GenerationError(
            503, "noc-inv-unavailable", "The investigation generator is unavailable."
        ) from None
    if contract.returncode != 0 or contract.stdout.strip() != "noc-inv-contract=1":
        raise GenerationError(
            503, "noc-inv-incompatible", "The investigation generator is incompatible."
        )
    try:
        staging_context = tempfile.TemporaryDirectory(
            prefix=".investigation-generation-", dir=profile.noc_root
        )
    except OSError:
        raise GenerationError(503, "storage-unavailable", "Investigation storage is unavailable.") from None

    with staging_context as temporary_directory:
        staging = Path(temporary_directory)
        output_directory = staging / "output"
        output_directory.mkdir(mode=0o700)
        argv = [
            str(executable),
            "--non-interactive",
            "--shift-date", request.shift_date,
            "--name", request.name,
            "--display-title", request.display_title,
            "--notebook-url", request.notebook_url,
            "--output-dir", str(output_directory),
        ]
        try:
            result = subprocess.run(
                argv,
                shell=False,
                cwd=profile.noc_root,
                timeout=profile.investigation_timeout_seconds,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                check=False,
                env=environment,
            )
        except subprocess.TimeoutExpired:
            raise GenerationError(504, "generation-timeout", "Investigation generation timed out.") from None
        except OSError:
            raise GenerationError(503, "noc-inv-unavailable", "The investigation generator is unavailable.") from None
        if result.returncode not in {0, 8}:
            failures = {
                2: (503, "noc-inv-incompatible", "The investigation generator is incompatible."),
                3: (422, "invalid-notebook-url", "FINAL Datadog Notebook URL is invalid."),
                4: (503, "storage-unavailable", "Investigation storage is unavailable."),
                5: (503, "copilot-unavailable", "GitHub Copilot CLI is unavailable."),
                6: (503, "datadog-mcp-unavailable", "Datadog MCP evidence retrieval is unavailable."),
                7: (504, "generation-timeout", "Investigation generation timed out."),
                9: (500, "storage-failed", "The investigation record could not be stored."),
            }
            status_code, code, message = failures.get(
                result.returncode,
                (500, "generation-failed", "Investigation generation failed."),
            )
            raise GenerationError(status_code, code, message)
        content, output_error = _read_output(output_directory / "investigation.md")
        if content is None:
            if output_error == "missing-output":
                raise GenerationError(
                    500,
                    "generated-output-missing",
                    "The investigation generator did not produce a safe record.",
                )
            raise GenerationError(
                500,
                "generated-output-invalid",
                "The investigation generator did not produce a safe record.",
            )

        content = _include_display_title(content, request.display_title)
        provenance, validation_errors = _validate_generated_record(content, request)
        if result.returncode == 8:
            validation_errors.append("noc_inv_validation")
        validation_status: ValidationStatus = (
            "ready_for_review" if not validation_errors else "needs_review"
        )
        published = staging / "published"
        published.mkdir(mode=0o700)
        record_file = published / "investigation.md"
        record_file.write_text(content, encoding="utf-8")
        generation_metadata = {
            "generationStatus": "completed",
            "validationStatus": validation_status,
            "validationIssues": validation_errors,
            "shiftDate": request.shift_date,
            "name": request.name,
            "displayTitle": request.display_title,
            "notebookUrl": request.notebook_url,
            "provenance": provenance or "unavailable",
        }
        (published / "generation-status.json").write_text(
            json.dumps(generation_metadata, indent=2) + "\n", encoding="utf-8"
        )
        target_parent = target.parent
        try:
            target_parent.mkdir(parents=True, exist_ok=True)
            target_parent.resolve(strict=True).relative_to(profile.noc_root.resolve())
            target.mkdir(mode=0o700)
        except FileExistsError:
            raise GenerationError(
                409,
                "investigation-conflict",
                "An investigation with this normalized name already exists.",
                field="name",
            ) from None
        except (OSError, ValueError):
            raise GenerationError(500, "storage-failed", "The investigation record could not be stored.") from None
        try:
            os.replace(published / "generation-status.json", target / "generation-status.json")
            os.replace(record_file, target / "investigation.md")
        except OSError:
            shutil.rmtree(target, ignore_errors=True)
            raise GenerationError(500, "storage-failed", "The investigation record could not be stored.") from None

    record = investigations.get_investigation(request.shift_date, request.name)
    if record is None:
        raise GenerationError(500, "record-unavailable", "The created investigation record is unavailable.")
    return InvestigationGenerationResult(
        generation_status="completed",
        validation_status=validation_status,
        review_state="unreviewed",
        record=record,
        error_code=None,
    )
