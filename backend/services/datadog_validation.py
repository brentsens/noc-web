"""Shared validation for untrusted Datadog responses."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit


DATADOG_HOST_SUFFIXES = (
    "datadoghq.com",
    "datadoghq.eu",
    "ddog-gov.com",
)
_TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_NUMERIC_IDENTIFIER_PATTERN = re.compile(r"^[1-9][0-9]{0,18}$")


class DatadogValidationError(ValueError):
    """Raised when Datadog data violates a required shape or bound."""

    def __init__(self, rule: str, category: str = "incident") -> None:
        self.rule = rule
        self.category = category
        super().__init__(rule)


def bounded_text(
    value: Any,
    *,
    maximum: int,
    rule: str,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str) or len(value) > maximum:
        raise DatadogValidationError(rule)
    if not allow_empty and not value.strip():
        raise DatadogValidationError(rule)
    if any(ord(character) < 32 and character not in "\t\n\r" for character in value):
        raise DatadogValidationError(rule)
    return value.strip()


def optional_text(value: Any, *, maximum: int, rule: str) -> str | None:
    if value is None:
        return None
    return bounded_text(value, maximum=maximum, rule=rule, allow_empty=True)


def timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not _TIMESTAMP_PATTERN.fullmatch(value):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def timestamp_string(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def is_datadog_host(host: str | None) -> bool:
    if not isinstance(host, str) or not host:
        return False
    normalized = host.casefold()
    return any(
        normalized == suffix or normalized.endswith(f".{suffix}")
        for suffix in DATADOG_HOST_SUFFIXES
    )


def validate_datadog_url(
    value: Any,
    *,
    rule: str,
    path_prefix: str | None = None,
) -> str:
    url = bounded_text(value, maximum=2048, rule=rule)
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise DatadogValidationError(rule) from None
    if (
        parsed.scheme != "https"
        or not is_datadog_host(parsed.hostname)
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or parsed.query
        or parsed.fragment
        or ".." in parsed.path.split("/")
    ):
        raise DatadogValidationError(rule)
    if path_prefix is not None and not parsed.path.startswith(path_prefix):
        raise DatadogValidationError(rule)
    return url


def validate_datadog_identifier(value: Any, *, rule: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_PATTERN.fullmatch(value):
        raise DatadogValidationError(rule)
    return value


def validate_numeric_identifier(value: Any, *, rule: str) -> str:
    if isinstance(value, bool):
        raise DatadogValidationError(rule)
    if isinstance(value, int):
        text = str(value)
    elif isinstance(value, str):
        text = value
    else:
        raise DatadogValidationError(rule)
    if not _NUMERIC_IDENTIFIER_PATTERN.fullmatch(text):
        raise DatadogValidationError(rule)
    return text


def bounded_list(value: Any, *, maximum: int, rule: str) -> list[Any]:
    if not isinstance(value, list) or len(value) > maximum:
        raise DatadogValidationError(rule)
    return value


def bounded_mapping(value: Any, *, maximum: int, rule: str) -> dict[str, Any]:
    if not isinstance(value, dict) or len(value) > maximum:
        raise DatadogValidationError(rule)
    if any(not isinstance(key, str) or not key for key in value):
        raise DatadogValidationError(rule)
    return value
