"""Read-only Datadog incident retrieval and shared short-lived cache."""

from __future__ import annotations

import fcntl
import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, BinaryIO, Callable
from urllib.parse import quote

from backend.services.datadog_provider import (
    DatadogClient,
    DatadogOperationRejected,
    DatadogProviderTimeout,
    DatadogProviderUnavailable,
    DatadogResponseInvalid,
    build_datadog_client,
)
from backend.services.datadog_validation import (
    DatadogValidationError,
    bounded_text as _bounded_text,
    timestamp as _timestamp,
    timestamp_string as _timestamp_string,
    validate_datadog_identifier,
    validate_datadog_url,
)
from backend.services.investigations import get_noc_root


logger = logging.getLogger(__name__)

CACHE_FILE_NAME = ".datadog-active-incidents.json"
REFRESH_INTERVAL_SECONDS = 60
MAX_INCIDENTS = 100
PROVIDER_NAME = "datadog-api"
_REQUIRED_INCIDENT_FIELDS = {"id", "title", "state"}
_OPTIONAL_INCIDENT_FIELDS = {
    "severity",
    "createdAt",
    "updatedAt",
    "summary",
    "url",
}
_ERROR_CODES = {
    "copilot-unavailable",
    "provider-unavailable",
    "timeout",
    "invalid-response",
    "cache-unavailable",
}

IncidentResponseInvalid = DatadogValidationError

_refresh_lock = threading.Lock()
_refreshing = False
_runtime_snapshots: dict[str, dict[str, Any]] = {}


class IncidentRefreshFailure(RuntimeError):
    """A redacted, controlled incident retrieval failure."""

    def __init__(self, code: str) -> None:
        self.code = code if code in _ERROR_CODES else "provider-unavailable"
        super().__init__(self.code)


def get_cache_file() -> Path:
    return get_noc_root() / CACHE_FILE_NAME


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_incident_url(value: Any) -> str:
    return validate_datadog_url(
        value,
        rule="invalid_incident_url",
        path_prefix="/incidents/",
    )


def validate_provider_response(response: Any) -> list[dict[str, str]]:
    """Validate and minimize a complete provider response; never repair it."""
    if not isinstance(response, dict):
        raise IncidentResponseInvalid("invalid_envelope_type", "envelope")
    if set(response) != {"incidents"}:
        raise IncidentResponseInvalid("unexpected_envelope_keys", "envelope")
    if not isinstance(response["incidents"], list):
        raise IncidentResponseInvalid("incidents_not_list", "envelope")
    if len(response["incidents"]) > MAX_INCIDENTS:
        raise IncidentResponseInvalid("too_many_incidents", "envelope")

    incidents: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    allowed_fields = _REQUIRED_INCIDENT_FIELDS | _OPTIONAL_INCIDENT_FIELDS
    for candidate in response["incidents"]:
        if not isinstance(candidate, dict):
            raise IncidentResponseInvalid("invalid_incident_type")
        keys = set(candidate)
        if not _REQUIRED_INCIDENT_FIELDS.issubset(keys):
            raise IncidentResponseInvalid("missing_required_incident_keys")
        if not keys.issubset(allowed_fields):
            raise IncidentResponseInvalid("unexpected_incident_keys")

        incident_id = _bounded_text(
            candidate["id"],
            maximum=128,
            rule="invalid_incident_id",
        )
        title = _bounded_text(
            candidate["title"],
            maximum=200,
            rule="invalid_incident_title",
        )
        state = candidate["state"]
        if not isinstance(state, str) or state.upper() not in {
            "ACTIVE",
            "STABLE",
            "RESOLVED",
        }:
            raise IncidentResponseInvalid("invalid_incident_state")
        if incident_id in seen_ids:
            raise IncidentResponseInvalid("duplicate_incident_id")
        seen_ids.add(incident_id)

        incident = {
            "id": incident_id,
            "title": title,
            "state": state,
        }
        if "severity" in candidate:
            incident["severity"] = _bounded_text(
                candidate["severity"],
                maximum=32,
                rule="invalid_incident_severity",
            )
        for field in ("createdAt", "updatedAt"):
            if field in candidate:
                timestamp = _bounded_text(
                    candidate[field],
                    maximum=40,
                    rule=f"invalid_incident_{field}",
                )
                if _timestamp(timestamp) is None:
                    raise IncidentResponseInvalid(f"invalid_incident_{field}")
                incident[field] = timestamp
        if "summary" in candidate:
            incident["summary"] = _bounded_text(
                candidate["summary"],
                maximum=500,
                rule="invalid_incident_summary",
                allow_empty=True,
            )
        if "url" in candidate:
            incident["url"] = _validate_incident_url(candidate["url"])
        if state.upper() in {"ACTIVE", "STABLE"}:
            incidents.append(incident)
    return incidents


def _optional_timestamp(value: Any, *, rule: str) -> str | None:
    if value is None:
        return None
    text = _bounded_text(value, maximum=40, rule=rule)
    if _timestamp(text) is None:
        raise IncidentResponseInvalid(rule)
    return text


def _map_search_incident(record: Any, app_base_url: str) -> dict[str, str] | None:
    if not isinstance(record, dict):
        raise IncidentResponseInvalid("invalid_search_record", "envelope")
    data = record.get("data")
    if not isinstance(data, dict):
        raise IncidentResponseInvalid("invalid_search_record", "envelope")
    incident_id = validate_datadog_identifier(
        data.get("id"),
        rule="invalid_incident_id",
    )
    attributes = data.get("attributes")
    if not isinstance(attributes, dict):
        raise IncidentResponseInvalid("invalid_search_record", "envelope")
    title = _bounded_text(
        attributes.get("title"),
        maximum=200,
        rule="invalid_incident_title",
    )
    state = attributes.get("state")
    if not isinstance(state, str) or state.upper() not in {
        "ACTIVE",
        "STABLE",
        "RESOLVED",
    }:
        raise IncidentResponseInvalid("invalid_incident_state")

    incident = {
        "id": incident_id,
        "title": title,
        "state": state,
    }
    if attributes.get("severity") is not None:
        incident["severity"] = _bounded_text(
            attributes["severity"],
            maximum=32,
            rule="invalid_incident_severity",
        )
    created_at = _optional_timestamp(
        attributes.get("created"),
        rule="invalid_incident_createdAt",
    )
    if created_at is not None:
        incident["createdAt"] = created_at
    updated_at = _optional_timestamp(
        attributes.get("modified"),
        rule="invalid_incident_updatedAt",
    )
    if updated_at is not None:
        incident["updatedAt"] = updated_at
    if attributes.get("customer_impact_scope") is not None:
        incident["summary"] = _bounded_text(
            attributes["customer_impact_scope"],
            maximum=500,
            rule="invalid_incident_summary",
            allow_empty=True,
        )
    url = (
        f"{app_base_url}/incidents/{quote(incident_id, safe='')}"
    )
    incident["url"] = _validate_incident_url(url)
    if state.upper() in {"ACTIVE", "STABLE"}:
        return incident
    return None


def _validate_search_total(value: Any, page_count: int) -> int:
    if value is None:
        return page_count
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise IncidentResponseInvalid("invalid_search_total", "envelope")
    if value > MAX_INCIDENTS:
        raise IncidentResponseInvalid("too_many_incidents", "envelope")
    if value < page_count:
        raise IncidentResponseInvalid("invalid_search_total", "envelope")
    return value


def retrieve_active_incidents(
    *,
    client: DatadogClient | None = None,
) -> dict[str, Any]:
    """Retrieve current incidents through the allowlisted Datadog client."""
    try:
        effective_client = client or build_datadog_client()
        incidents: list[dict[str, str]] = []
        collected_records = 0
        offset: int | None = None
        expected_total: int | None = None
        while True:
            payload = effective_client.search_incidents(offset=offset)
            data = payload.get("data")
            if not isinstance(data, dict):
                raise IncidentResponseInvalid("invalid_search_envelope", "envelope")
            attributes = data.get("attributes")
            if not isinstance(attributes, dict):
                raise IncidentResponseInvalid("invalid_search_envelope", "envelope")
            page = attributes.get("incidents")
            if not isinstance(page, list):
                raise IncidentResponseInvalid("incidents_not_list", "envelope")
            if len(page) > MAX_INCIDENTS:
                raise IncidentResponseInvalid("too_many_incidents", "envelope")
            expected_total = _validate_search_total(
                attributes.get("total"),
                len(page) if expected_total is None else expected_total,
            )
            collected_records += len(page)
            for record in page:
                mapped = _map_search_incident(
                    record,
                    effective_client.app_base_url,
                )
                if mapped is not None:
                    incidents.append(mapped)
            if len(incidents) > MAX_INCIDENTS:
                raise IncidentResponseInvalid("too_many_incidents", "envelope")

            pagination = (
                payload.get("meta", {})
                .get("pagination", {})
                if isinstance(payload.get("meta"), dict)
                else {}
            )
            next_offset = pagination.get("next_offset")
            if next_offset is None:
                break
            if (
                isinstance(next_offset, bool)
                or not isinstance(next_offset, int)
                or next_offset <= (offset or 0)
                or next_offset >= MAX_INCIDENTS
            ):
                raise IncidentResponseInvalid("invalid_pagination", "envelope")
            if expected_total is not None and next_offset >= expected_total:
                break
            offset = next_offset

        if expected_total is not None and collected_records != expected_total:
            raise IncidentResponseInvalid("incomplete_search", "envelope")
        return {"incidents": validate_provider_response({"incidents": incidents})}
    except IncidentRefreshFailure:
        raise
    except IncidentResponseInvalid:
        raise
    except DatadogProviderTimeout:
        raise IncidentRefreshFailure("timeout") from None
    except DatadogProviderUnavailable:
        raise IncidentRefreshFailure("provider-unavailable") from None
    except DatadogResponseInvalid as error:
        raise IncidentResponseInvalid(error.rule, "envelope") from None
    except DatadogOperationRejected:
        raise IncidentResponseInvalid("operation_rejected", "envelope") from None
    except DatadogValidationError as error:
        raise IncidentResponseInvalid(error.rule, error.category) from None
    except Exception:
        raise IncidentRefreshFailure("provider-unavailable") from None


def _empty_cache() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "incidents": [],
        "lastAttemptedAt": None,
        "lastSuccessfulAt": None,
        "freshness": "unavailable",
        "error": None,
    }


def _read_cache(cache_file: Path) -> dict[str, Any]:
    try:
        raw = json.loads(cache_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _empty_cache()
    except (OSError, UnicodeError, json.JSONDecodeError):
        cache = _empty_cache()
        cache["error"] = "cache-unavailable"
        return cache

    if (
        not isinstance(raw, dict)
        or set(raw)
        != {
            "schemaVersion",
            "incidents",
            "lastAttemptedAt",
            "lastSuccessfulAt",
            "freshness",
            "error",
        }
        or isinstance(raw["schemaVersion"], bool)
        or not isinstance(raw["schemaVersion"], int)
        or raw["schemaVersion"] != 1
        or not isinstance(raw["freshness"], str)
        or raw["freshness"] not in {"current", "stale", "unavailable"}
        or (
            raw["error"] is not None
            and not isinstance(raw["error"], str)
        )
        or raw["error"] not in {None, *_ERROR_CODES}
    ):
        cache = _empty_cache()
        cache["error"] = "cache-unavailable"
        return cache

    try:
        incidents = validate_provider_response({"incidents": raw["incidents"]})
    except IncidentResponseInvalid:
        cache = _empty_cache()
        cache["error"] = "cache-unavailable"
        return cache
    if incidents != raw["incidents"]:
        cache = _empty_cache()
        cache["error"] = "cache-unavailable"
        return cache

    attempted = raw["lastAttemptedAt"]
    successful = raw["lastSuccessfulAt"]
    if (
        (attempted is not None and _timestamp(attempted) is None)
        or (successful is not None and _timestamp(successful) is None)
        or (successful is not None and attempted is None)
        or (
            successful is None
            and (incidents or raw["freshness"] != "unavailable")
        )
        or (
            successful is not None
            and raw["freshness"] == "unavailable"
        )
    ):
        cache = _empty_cache()
        cache["error"] = "cache-unavailable"
        return cache
    return {
        "schemaVersion": 1,
        "incidents": incidents,
        "lastAttemptedAt": attempted,
        "lastSuccessfulAt": successful,
        "freshness": raw["freshness"],
        "error": raw["error"],
    }


def _write_cache(cache_file: Path, cache: dict[str, Any]) -> None:
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=cache_file.parent,
            prefix=f".{cache_file.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            os.fchmod(temporary.fileno(), 0o600)
            json.dump(cache, temporary, ensure_ascii=False, separators=(",", ":"))
            temporary.write("\n")
        os.replace(temporary_path, cache_file)
    except OSError:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except OSError:
                pass
        raise


def _cache_path(cache_file: str | Path | None) -> Path:
    return get_cache_file() if cache_file is None else Path(cache_file)


def _acquire_refresh_lock(cache_file: Path) -> BinaryIO | None:
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file = cache_file.with_name(f"{cache_file.name}.lock").open("a+b")
    try:
        os.fchmod(lock_file.fileno(), 0o600)
        try:
            fcntl.flock(
                lock_file.fileno(),
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )
        except BlockingIOError:
            lock_file.close()
            return None
    except OSError:
        lock_file.close()
        raise
    return lock_file


def _refresh_lock_is_held(cache_file: Path) -> bool:
    lock_path = cache_file.with_name(f"{cache_file.name}.lock")
    try:
        lock_file = lock_path.open("r+b")
    except OSError:
        return False
    try:
        try:
            fcntl.flock(
                lock_file.fileno(),
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )
        except BlockingIOError:
            return True
        except OSError:
            return False
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        return False
    except OSError:
        return False
    finally:
        lock_file.close()


def _release_refresh_lock(lock_file: BinaryIO) -> None:
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    finally:
        lock_file.close()


def _snapshot_response(
    cache: dict[str, Any],
    *,
    now: datetime | None = None,
    refreshing: bool = False,
) -> dict[str, Any]:
    current_time = now or _utc_now()
    last_attempt = _timestamp(cache["lastAttemptedAt"])
    last_success = _timestamp(cache["lastSuccessfulAt"])
    if last_success is None:
        freshness = "unavailable"
    elif (
        cache["error"] is not None
        or (last_attempt is not None and last_attempt > last_success)
        or current_time - last_success >= timedelta(seconds=REFRESH_INTERVAL_SECONDS)
        or cache["freshness"] == "stale"
    ):
        freshness = "stale"
    else:
        freshness = "current"
    if refreshing:
        freshness = "refreshing"
    return {
        "incidents": cache["incidents"],
        "count": len(cache["incidents"]) if last_success is not None else None,
        "lastAttemptedAt": cache["lastAttemptedAt"],
        "lastSuccessfulAt": cache["lastSuccessfulAt"],
        "freshness": freshness,
        "error": cache["error"],
    }


def _newer_cache(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    first_time = _timestamp(first.get("lastAttemptedAt"))
    second_time = _timestamp(second.get("lastAttemptedAt"))
    if first_time is None:
        return second
    if second_time is None:
        return first
    return first if first_time >= second_time else second


def _read_current_cache(cache_file: Path) -> dict[str, Any]:
    cache = _read_cache(cache_file)
    runtime = _runtime_snapshots.get(str(cache_file))
    return _newer_cache(cache, runtime) if runtime is not None else cache


def get_incident_snapshot(
    cache_file: str | Path | None = None,
    *,
    now: datetime | None = None,
    schedule_refresh: bool = True,
) -> dict[str, Any]:
    path = _cache_path(cache_file)
    with _refresh_lock:
        refreshing = _refreshing
    refreshing = refreshing or _refresh_lock_is_held(path)
    cache = _read_current_cache(path)
    response = _snapshot_response(cache, now=now, refreshing=refreshing)
    if schedule_refresh and not refreshing:
        scheduled = schedule_refresh_if_due(path, now=now)
        with _refresh_lock:
            refreshing = _refreshing
        refreshing = refreshing or _refresh_lock_is_held(path)
        scheduled_refreshing = (
            isinstance(scheduled, dict)
            and scheduled.get("freshness") == "refreshing"
        )
        if refreshing or scheduled_refreshing:
            response = _snapshot_response(
                _read_current_cache(path),
                now=now,
                refreshing=True,
            )
        else:
            response = _snapshot_response(
                _read_current_cache(path),
                now=now,
            )
    return response


def _failure_snapshot(
    previous: dict[str, Any],
    *,
    attempted_at: str,
    code: str,
) -> dict[str, Any]:
    has_success = previous["lastSuccessfulAt"] is not None
    return {
        "schemaVersion": 1,
        "incidents": previous["incidents"] if has_success else [],
        "lastAttemptedAt": attempted_at,
        "lastSuccessfulAt": previous["lastSuccessfulAt"],
        "freshness": "stale" if has_success else "unavailable",
        "error": code,
    }


def refresh_incident_cache(
    cache_file: str | Path | None = None,
    *,
    provider: Callable[[], Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    path = _cache_path(cache_file)
    previous = _read_current_cache(path)
    attempted = now or _utc_now()
    attempted_at = _timestamp_string(attempted)

    in_progress = {
        **previous,
        "lastAttemptedAt": attempted_at,
        "freshness": (
            "stale" if previous["lastSuccessfulAt"] is not None else "unavailable"
        ),
        "error": None,
    }
    try:
        _write_cache(path, in_progress)
    except OSError:
        failure = _failure_snapshot(
            previous,
            attempted_at=attempted_at,
            code="cache-unavailable",
        )
        _runtime_snapshots[str(path)] = failure
        return _snapshot_response(failure, now=now)

    validation_error = None
    try:
        result = (provider or retrieve_active_incidents)()
        incidents = validate_provider_response(result)
    except IncidentResponseInvalid as error:
        validation_error = error
        code = "invalid-response"
    except IncidentRefreshFailure as error:
        code = error.code
    except Exception:
        code = "provider-unavailable"
    else:
        successful_at = _timestamp_string(now or _utc_now())
        success = {
            "schemaVersion": 1,
            "incidents": incidents,
            "lastAttemptedAt": attempted_at,
            "lastSuccessfulAt": successful_at,
            "freshness": "current",
            "error": None,
        }
        try:
            _write_cache(path, success)
        except OSError:
            failure = _failure_snapshot(
                previous,
                attempted_at=attempted_at,
                code="cache-unavailable",
            )
            _runtime_snapshots[str(path)] = failure
            logger.warning("Datadog incident refresh failed: code=cache-unavailable")
            return _snapshot_response(failure, now=now)
        _runtime_snapshots[str(path)] = success
        return _snapshot_response(success, now=now)

    failure = _failure_snapshot(previous, attempted_at=attempted_at, code=code)
    try:
        _write_cache(path, failure)
    except OSError:
        failure["error"] = "cache-unavailable"
    _runtime_snapshots[str(path)] = failure
    if validation_error is not None:
        logger.warning(
            "Datadog incident refresh failed: code=%s "
            "provider=%s rule=%s category=%s providerStatus=invalid",
            failure["error"],
            PROVIDER_NAME,
            validation_error.rule,
            validation_error.category,
        )
    else:
        logger.warning(
            "Datadog incident refresh failed: code=%s provider=%s",
            failure["error"],
            PROVIDER_NAME,
        )
    return _snapshot_response(failure, now=now)


def _background_refresh(path: Path, lock_file: BinaryIO) -> None:
    global _refreshing
    try:
        refresh_incident_cache(path)
    finally:
        try:
            _release_refresh_lock(lock_file)
        except OSError:
            logger.warning("Datadog incident refresh lock release failed")
        with _refresh_lock:
            _refreshing = False


def request_refresh(
    *,
    cache_file: str | Path | None = None,
    provider: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    global _refreshing
    path = _cache_path(cache_file)
    with _refresh_lock:
        if _refreshing:
            return _snapshot_response(
                _read_current_cache(path),
                refreshing=True,
            )
        try:
            process_lock = _acquire_refresh_lock(path)
        except OSError:
            previous = _read_current_cache(path)
            failure = _failure_snapshot(
                previous,
                attempted_at=_timestamp_string(_utc_now()),
                code="cache-unavailable",
            )
            _runtime_snapshots[str(path)] = failure
            logger.warning("Datadog incident refresh failed: code=cache-unavailable")
            return _snapshot_response(failure)
        if process_lock is None:
            return _snapshot_response(
                _read_current_cache(path),
                refreshing=True,
            )
        _refreshing = True
        try:
            worker = threading.Thread(
                target=_background_refresh,
                args=(path, process_lock),
                kwargs={},
                daemon=True,
            )
            if provider is not None:
                worker = threading.Thread(
                    target=_run_background_provider,
                    args=(path, provider, process_lock),
                    daemon=True,
                )
            worker.start()
        except RuntimeError:
            _refreshing = False
            try:
                _release_refresh_lock(process_lock)
            except OSError:
                logger.warning("Datadog incident refresh lock release failed")
            failure = _failure_snapshot(
                _read_current_cache(path),
                attempted_at=_timestamp_string(_utc_now()),
                code="provider-unavailable",
            )
            _runtime_snapshots[str(path)] = failure
            return _snapshot_response(failure)
    return get_incident_snapshot(path, schedule_refresh=False)


def _run_background_provider(
    path: Path,
    provider: Callable[[], Any],
    lock_file: BinaryIO,
) -> None:
    global _refreshing
    try:
        refresh_incident_cache(path, provider=provider)
    finally:
        try:
            _release_refresh_lock(lock_file)
        except OSError:
            logger.warning("Datadog incident refresh lock release failed")
        with _refresh_lock:
            _refreshing = False


def schedule_refresh_if_due(
    cache_file: str | Path | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    path = _cache_path(cache_file)
    cache = _read_current_cache(path)
    last_attempt = _timestamp(cache["lastAttemptedAt"])
    current_time = now or _utc_now()
    due = (
        last_attempt is None
        or current_time - last_attempt
        >= timedelta(seconds=REFRESH_INTERVAL_SECONDS)
    )
    if due:
        return request_refresh(cache_file=path)
    return _snapshot_response(cache, now=now)
