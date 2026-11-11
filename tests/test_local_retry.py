import json
from pathlib import Path

import pytest

from backend.services import local_retry


def _snapshot(**overrides):
    values = {
        "workflow": "assistant",
        "shiftDate": "2099-12-31",
        "identity": None,
        "provider": "ollama",
        "model": "qwen3:8b",
        "payload": {"envelope": {"question": "status", "evidence": [{"id": "status"}]}},
    }
    values.update(overrides)
    return values


def test_token_is_opaque_and_metadata_is_bounded():
    store = local_retry.LocalRetryStore()

    availability = store.put(_snapshot())

    assert set(availability) == {"available", "retryToken", "expiresAt", "provider", "model"}
    assert availability["available"] is True
    assert availability["retryToken"]
    assert "payload" not in json.dumps(availability)
    assert "envelope" not in json.dumps(availability)


def test_snapshot_is_single_use_and_exact():
    store = local_retry.LocalRetryStore()
    availability = store.put(_snapshot())
    payload = _snapshot()["payload"]

    consumed = store.consume(
        availability["retryToken"],
        workflow="assistant",
        shift_date="2099-12-31",
    )

    assert consumed["payload"] == payload
    with pytest.raises(local_retry.RetrySnapshotError) as error:
        store.consume(
            availability["retryToken"],
            workflow="assistant",
            shift_date="2099-12-31",
        )
    assert error.value.code == "retry-snapshot-used"


def test_missing_expired_and_mismatched_tokens_fail_closed():
    now = [1000.0]
    store = local_retry.LocalRetryStore(clock=lambda: now[0], ttl_seconds=600)
    availability = store.put(_snapshot())

    with pytest.raises(local_retry.RetrySnapshotError) as unavailable:
        store.consume("missing", workflow="assistant", shift_date="2099-12-31")
    assert unavailable.value.code == "retry-snapshot-unavailable"

    with pytest.raises(local_retry.RetrySnapshotError) as mismatch:
        store.consume(
            availability["retryToken"],
            workflow="handover",
            shift_date="2099-12-31",
        )
    assert mismatch.value.code == "retry-snapshot-unavailable"

    now[0] = 1600.0
    with pytest.raises(local_retry.RetrySnapshotError) as expired:
        store.consume(
            availability["retryToken"],
            workflow="assistant",
            shift_date="2099-12-31",
        )
    assert expired.value.code == "retry-snapshot-expired"


def test_store_is_bounded_to_thirty_two_entries():
    store = local_retry.LocalRetryStore(clock=lambda: 1000.0)
    first = store.put(_snapshot())
    for _ in range(32):
        store.put(_snapshot())

    with pytest.raises(local_retry.RetrySnapshotError):
        store.consume(
            first["retryToken"],
            workflow="assistant",
            shift_date="2099-12-31",
        )


def test_store_never_persists_to_disk(tmp_path):
    store = local_retry.LocalRetryStore()
    before = {path for path in Path(tmp_path).rglob("*")}
    store.put(_snapshot())
    after = {path for path in Path(tmp_path).rglob("*")}

    assert before == after


def test_capture_requires_a_configured_local_provider(monkeypatch):
    from backend.services import ai_provider

    monkeypatch.setattr(
        ai_provider,
        "resolve_local_provider_runtime",
        lambda: ai_provider.ProviderRuntime(
            identifier="ollama",
            provider=None,
            readiness={"readiness": "notConfigured"},
        ),
    )
    assert local_retry.capture_local_retry(
        workflow="assistant",
        shift_date="2099-12-31",
        payload={},
        store=local_retry.LocalRetryStore(),
    ) is None
