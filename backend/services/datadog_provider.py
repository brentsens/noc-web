"""Read-only Datadog API provider with static readiness and a fixed allowlist."""

from __future__ import annotations

import json
import os
import socket
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from backend.services.datadog_validation import (
    DatadogValidationError,
    is_datadog_host,
    validate_datadog_identifier,
    validate_numeric_identifier,
)


PROVIDER_ID = "datadog-api"
PROVIDER_LABEL = "Datadog API"
DEFAULT_BASE_URL = "https://api.datadoghq.com"
DEFAULT_TIMEOUT_SECONDS = 90
MAX_TIMEOUT_SECONDS = 120
MAX_RESPONSE_BYTES = 1_000_000
_ACCEPTED_JSON_MEDIA_TYPES = frozenset({
    "application/json",
    "application/vnd.api+json",
})
READY = "ready"
NOT_READY = "notReady"
NOT_CONFIGURED = "notConfigured"

INCIDENT_SEARCH_PATH = "/api/v2/incidents/search"
INCIDENT_DETAIL_PATH = "/api/v2/incidents/{incident_id}"
NOTEBOOK_DETAIL_PATH = "/api/v1/notebooks/{notebook_id}"
MONITOR_DETAIL_PATH = "/api/v1/monitor/{monitor_id}"

_OPERATIONS = {
    "search_incidents": ("GET", INCIDENT_SEARCH_PATH),
    "get_incident": ("GET", INCIDENT_DETAIL_PATH),
    "get_notebook": ("GET", NOTEBOOK_DETAIL_PATH),
    "get_monitor": ("GET", MONITOR_DETAIL_PATH),
}


class DatadogConfigurationError(ValueError):
    """A redacted Datadog configuration error naming only the setting."""

    def __init__(self, setting: str) -> None:
        super().__init__(f"The {setting} setting is invalid.")
        self.setting = setting


class DatadogProviderError(RuntimeError):
    code = "provider-unavailable"


class DatadogProviderUnavailable(DatadogProviderError):
    code = "provider-unavailable"


class DatadogProviderTimeout(DatadogProviderError):
    code = "timeout"


class DatadogResponseInvalid(DatadogProviderError, DatadogValidationError):
    code = "invalid-response"

    def __init__(self, rule: str) -> None:
        DatadogValidationError.__init__(self, rule)
        self.rule = rule


class DatadogResourceNotFound(DatadogProviderUnavailable):
    code = "not-found"


class DatadogForbidden(DatadogProviderUnavailable):
    code = "forbidden"


class DatadogOperationRejected(DatadogProviderError):
    code = "invalid-response"


@dataclass(frozen=True)
class DatadogConfiguration:
    base_url: str
    timeout_seconds: int
    credential_present: bool

    @property
    def app_base_url(self) -> str:
        parsed = urlsplit(self.base_url)
        host = parsed.hostname or ""
        app_host = (
            f"app.{host[4:]}"
            if host.startswith("api.")
            else f"app.{host}"
        )
        return f"https://{app_host}"


@dataclass(frozen=True)
class DatadogResponse:
    status: int
    body: bytes
    content_type: str | None = None


DatadogTransport = Callable[
    [str, str, dict[str, str], bytes | None, float],
    DatadogResponse,
]


def _environment(environ: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if environ is None else environ


def access_token(environ: Mapping[str, str] | None = None) -> str:
    value = _environment(environ).get("NOC_WEB_DATADOG_ACCESS_TOKEN", "")
    return value.strip() if isinstance(value, str) else ""


def _validate_base_url(value: str) -> str:
    if not isinstance(value, str):
        raise DatadogConfigurationError("NOC_WEB_DATADOG_BASE_URL")
    candidate = value.strip().rstrip("/")
    if not candidate:
        raise DatadogConfigurationError("NOC_WEB_DATADOG_BASE_URL")
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError:
        raise DatadogConfigurationError("NOC_WEB_DATADOG_BASE_URL") from None
    host = parsed.hostname
    if (
        parsed.scheme != "https"
        or not host
        or not host.casefold().split(".")[0] == "api"
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or ".." in parsed.path.split("/")
    ):
        raise DatadogConfigurationError("NOC_WEB_DATADOG_BASE_URL")
    if not is_datadog_host(host):
        raise DatadogConfigurationError("NOC_WEB_DATADOG_BASE_URL")
    return f"https://{host.casefold()}"


def _validate_timeout(value: str | None) -> int:
    if value is None or not str(value).strip():
        return DEFAULT_TIMEOUT_SECONDS
    try:
        timeout = int(str(value).strip())
    except (TypeError, ValueError):
        raise DatadogConfigurationError("NOC_WEB_DATADOG_TIMEOUT_SECONDS") from None
    if not 1 <= timeout <= MAX_TIMEOUT_SECONDS:
        raise DatadogConfigurationError("NOC_WEB_DATADOG_TIMEOUT_SECONDS")
    return timeout


def load_datadog_configuration(
    environ: Mapping[str, str] | None = None,
) -> DatadogConfiguration:
    source = _environment(environ)
    return DatadogConfiguration(
        base_url=_validate_base_url(
            source.get("NOC_WEB_DATADOG_BASE_URL", DEFAULT_BASE_URL)
        ),
        timeout_seconds=_validate_timeout(
            source.get("NOC_WEB_DATADOG_TIMEOUT_SECONDS")
        ),
        credential_present=bool(access_token(source)),
    )


def datadog_provider_readiness(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return static readiness without making a Datadog request."""
    source = _environment(environ)
    try:
        configuration = load_datadog_configuration(source)
    except DatadogConfigurationError as error:
        credential_present = bool(access_token(source))
        return {
            "provider": PROVIDER_ID,
            "configuredProvider": PROVIDER_ID if credential_present else None,
            "baseUrl": DEFAULT_BASE_URL,
            "readiness": NOT_READY,
            "label": PROVIDER_LABEL,
            "credentialPresent": credential_present,
            "impact": "Datadog evidence retrieval configuration is invalid.",
            "correctiveAction": (
                f"Correct the {error.setting} setting and restart NOC Web."
            ),
        }

    if not configuration.credential_present:
        return {
            "provider": PROVIDER_ID,
            "configuredProvider": None,
            "baseUrl": configuration.base_url,
            "readiness": NOT_CONFIGURED,
            "label": PROVIDER_LABEL,
            "credentialPresent": False,
            "impact": "Live Datadog incident and evidence retrieval is not configured.",
            "correctiveAction": (
                "Set NOC_WEB_DATADOG_ACCESS_TOKEN in the process environment "
                "and restart NOC Web."
            ),
        }

    return {
        "provider": PROVIDER_ID,
        "configuredProvider": PROVIDER_ID,
        "baseUrl": configuration.base_url,
        "readiness": READY,
        "label": PROVIDER_LABEL,
        "credentialPresent": True,
        "impact": "Live Datadog incident and evidence retrieval is configured.",
        "correctiveAction": "No action required.",
    }


class _NoRedirectHandler(HTTPRedirectHandler):
    """Refuse redirects so the authorization header is never forwarded."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_opener = build_opener(_NoRedirectHandler)


def _default_transport(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None,
    timeout: float,
) -> DatadogResponse:
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with _opener.open(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            content_type = response.headers.get("Content-Type")
            payload = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        if 300 <= error.code <= 399:
            raise DatadogProviderUnavailable(
                "The Datadog provider is unavailable."
            ) from None
        if error.code == 404:
            raise DatadogResourceNotFound("The Datadog resource was not found.") from None
        if error.code == 403:
            raise DatadogForbidden("The Datadog request was forbidden.") from None
        if error.code in {401, 429} or 500 <= error.code <= 599:
            raise DatadogProviderUnavailable(
                "The Datadog provider is unavailable."
            ) from None
        raise DatadogResponseInvalid("datadog_http_status") from None
    except URLError as error:
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            raise DatadogProviderTimeout("The Datadog request timed out.") from None
        raise DatadogProviderUnavailable("The Datadog provider is unavailable.") from None
    except (TimeoutError, socket.timeout):
        raise DatadogProviderTimeout("The Datadog request timed out.") from None
    except (OSError, ValueError):
        raise DatadogProviderUnavailable("The Datadog provider is unavailable.") from None

    if len(payload) > MAX_RESPONSE_BYTES:
        raise DatadogResponseInvalid("datadog_response_too_large")
    return DatadogResponse(status=status, body=payload, content_type=content_type)


def _validate_content_type(content_type: str | None) -> None:
    if content_type is None:
        return
    media_type = content_type.split(";", 1)[0].strip().casefold()
    if media_type not in _ACCEPTED_JSON_MEDIA_TYPES:
        raise DatadogResponseInvalid("datadog_content_type")


class DatadogClient:
    """Only the allowlisted read-only operations can reach the transport."""

    def __init__(
        self,
        configuration: DatadogConfiguration,
        token: str,
        *,
        transport: DatadogTransport | None = None,
        deadline: float | None = None,
    ) -> None:
        self._configuration = configuration
        self._token = token
        self._transport = transport or _default_transport
        self._deadline = (
            time.monotonic() + configuration.timeout_seconds
            if deadline is None
            else deadline
        )

    def __repr__(self) -> str:
        return (
            "DatadogClient("
            f"base_url={self._configuration.base_url!r}, "
            f"credential_present={self._configuration.credential_present!r})"
        )

    @property
    def app_base_url(self) -> str:
        return self._configuration.app_base_url

    def _request(
        self,
        operation: str,
        path_values: Mapping[str, str] | None = None,
        query: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        definition = _OPERATIONS.get(operation)
        if definition is None:
            raise DatadogOperationRejected("The Datadog operation is not allowed.")
        method, template = definition
        path = template
        for name, value in (path_values or {}).items():
            path = path.replace("{" + name + "}", quote(value, safe=""))
        url = f"{self._configuration.base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"

        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise DatadogProviderTimeout("The Datadog request timed out.")
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
        }
        response = self._transport(method, url, headers, None, remaining)
        if response.status != 200:
            if 300 <= response.status <= 399:
                raise DatadogProviderUnavailable(
                    "The Datadog provider is unavailable."
                )
            if response.status == 404:
                raise DatadogResourceNotFound("The Datadog resource was not found.")
            if response.status == 403:
                raise DatadogForbidden("The Datadog request was forbidden.")
            if response.status in {401, 429} or 500 <= response.status <= 599:
                raise DatadogProviderUnavailable("The Datadog provider is unavailable.")
            raise DatadogResponseInvalid("datadog_http_status")
        _validate_content_type(response.content_type)
        if len(response.body) > MAX_RESPONSE_BYTES:
            raise DatadogResponseInvalid("datadog_response_too_large")
        try:
            text = response.body.decode("utf-8")
        except UnicodeDecodeError:
            raise DatadogResponseInvalid("datadog_response_encoding") from None
        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            raise DatadogResponseInvalid("datadog_response_json") from None
        if not isinstance(payload, dict):
            raise DatadogResponseInvalid("datadog_response_type")
        return payload

    def search_incidents(
        self,
        *,
        offset: int | None = None,
        page_size: int = 100,
    ) -> dict[str, Any]:
        if (
            isinstance(page_size, bool)
            or not isinstance(page_size, int)
            or not 1 <= page_size <= 100
        ):
            raise DatadogResponseInvalid("invalid_page_size")
        if offset is not None and (
            isinstance(offset, bool)
            or not isinstance(offset, int)
            or not 0 <= offset < 100
        ):
            raise DatadogResponseInvalid("invalid_page_offset")
        query = {
            "query": "state:(active OR stable)",
            "page[size]": str(page_size),
        }
        if offset is not None:
            query["page[offset]"] = str(offset)
        return self._request("search_incidents", query=query)

    def get_incident(self, incident_id: str) -> dict[str, Any]:
        identifier = validate_datadog_identifier(
            incident_id,
            rule="invalid_incident_id",
        )
        return self._request(
            "get_incident",
            {"incident_id": identifier},
            {"include": "attachments"},
        )

    def get_notebook(self, notebook_id: str | int) -> dict[str, Any]:
        identifier = validate_numeric_identifier(
            notebook_id,
            rule="invalid_notebook_id",
        )
        return self._request("get_notebook", {"notebook_id": identifier})

    def get_monitor(self, monitor_id: str | int) -> dict[str, Any]:
        identifier = validate_numeric_identifier(
            monitor_id,
            rule="invalid_monitor_id",
        )
        return self._request(
            "get_monitor",
            {"monitor_id": identifier},
            {"group_states": "all", "with_assets": "true"},
        )


def build_datadog_client(
    *,
    environ: Mapping[str, str] | None = None,
    transport: DatadogTransport | None = None,
    configuration: DatadogConfiguration | None = None,
) -> DatadogClient:
    source = _environment(environ)
    token = access_token(source)
    if not token:
        raise DatadogProviderUnavailable(
            "The Datadog provider is not configured."
        )
    try:
        effective = configuration or load_datadog_configuration(source)
    except DatadogConfigurationError:
        raise DatadogProviderUnavailable(
            "The Datadog provider is not configured."
        ) from None
    return DatadogClient(
        effective,
        token,
        transport=transport,
    )
