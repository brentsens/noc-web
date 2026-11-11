import pytest

from backend.services.investigation_preview_store import (
    InvestigationPreviewStore,
    PreviewStoreError,
)
from tests.support.investigation_ai import Clock


def _snapshot(value="one"):
    return {"request": {"name": value}, "package": {"value": value}}


def test_store_is_single_use_and_does_not_persist():
    store = InvestigationPreviewStore()
    entry = store.put(_snapshot())
    consumed = store.consume(entry["previewId"])

    assert consumed["package"] == {"value": "one"}
    with pytest.raises(PreviewStoreError) as error:
        store.consume(entry["previewId"])
    assert error.value.code == "preview-used"


def test_store_expires_entries_with_injected_clock():
    clock = Clock()
    store = InvestigationPreviewStore(clock=clock)
    entry = store.put(_snapshot())
    clock.advance(10 * 60 + 1)

    with pytest.raises(PreviewStoreError) as error:
        store.consume(entry["previewId"])

    assert error.value.code == "preview-expired"


def test_store_evicts_oldest_entries_at_capacity():
    clock = Clock()
    store = InvestigationPreviewStore(clock=clock, maximum_entries=2)
    first = store.put(_snapshot("first"))
    clock.advance(1)
    second = store.put(_snapshot("second"))
    clock.advance(1)
    third = store.put(_snapshot("third"))

    assert store.consume(second["previewId"])["package"]["value"] == "second"
    assert store.consume(third["previewId"])["package"]["value"] == "third"
    with pytest.raises(PreviewStoreError):
        store.consume(first["previewId"])


def test_store_rejects_unknown_and_empty_preview_ids():
    store = InvestigationPreviewStore()
    for value in ("", "unknown"):
        with pytest.raises(PreviewStoreError) as error:
            store.consume(value)
        assert error.value.code == "preview-required"


def test_store_can_be_invalidated_and_cleared():
    store = InvestigationPreviewStore()
    entry = store.put(_snapshot())
    store.invalidate(entry["previewId"])
    with pytest.raises(PreviewStoreError):
        store.consume(entry["previewId"])
    store.put(_snapshot())
    store.clear()
    with pytest.raises(PreviewStoreError):
        store.consume("anything")
