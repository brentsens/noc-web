import json

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.services import ai_provider, assistant
from backend.services.copilot_mcp import CopilotProviderTimeout


SHIFT = "2099-12-31"


def _evidence():
    return [{
        "id": "jira-cache",
        "kind": "jira-cache",
        "provenance": "noc-web",
        "availability": "available",
        "freshness": "current",
        "summary": {"tickets": []},
    }]


def _configure_primary_failure(monkeypatch):
    calls = []

    def provider(envelope):
        calls.append(envelope)
        raise CopilotProviderTimeout("primary timed out")

    monkeypatch.setattr(app.state, "assistant_provider", provider)
    monkeypatch.setattr(app.state, "assistant_provider_identifier", "deepseek-api")
    monkeypatch.setattr(assistant, "collect_context", lambda _shift: _evidence())
    return calls


def _configure_local(monkeypatch, output=None):
    monkeypatch.setenv("NOC_WEB_OLLAMA_BASE_URL", "http://ollama.lan:11434")
    monkeypatch.setenv("NOC_WEB_OLLAMA_MODEL", "qwen3:8b")
    calls = []
    local_output = output or {"aiObservations": [], "recommendations": []}

    def builder(configuration, *, system_prompt=None):
        def provider(envelope):
            calls.append({"envelope": envelope, "model": configuration.model})
            return local_output

        return provider

    monkeypatch.setattr(ai_provider, "build_ollama_provider", builder)
    return calls


def test_assistant_primary_failure_offers_retry_only_after_explicit_confirmation(monkeypatch):
    primary_calls = _configure_primary_failure(monkeypatch)
    local_calls = _configure_local(monkeypatch)
    client = TestClient(app)

    failed = client.post(f"/api/shifts/{SHIFT}/assistant/questions", json={
        "shiftDate": SHIFT,
        "question": "What should I focus on?",
        "providerDisclosureAcknowledged": True,
    })

    assert failed.status_code == 200
    body = failed.json()
    assert body["providerStatus"] == "timeout"
    assert body["localRetry"]["available"] is True
    assert body["localRetry"]["provider"] == "ollama"
    assert body["localRetry"]["model"] == "qwen3:8b"
    assert len(primary_calls) == 1
    assert local_calls == []

    retry_token = body["localRetry"]["retryToken"]
    unconfirmed = client.post(
        f"/api/shifts/{SHIFT}/assistant/questions/local-retry",
        json={"retryToken": retry_token, "confirmed": False},
    )
    assert unconfirmed.status_code == 422
    assert local_calls == []

    retried = client.post(
        f"/api/shifts/{SHIFT}/assistant/questions/local-retry",
        json={"retryToken": retry_token, "confirmed": True},
    )
    assert retried.status_code == 200
    retried_body = retried.json()
    assert retried_body["provider"] == "ollama"
    assert retried_body["providerStatus"] == "success"
    assert retried_body["shiftDate"] == SHIFT
    assert local_calls[0]["model"] == "qwen3:8b"
    assert local_calls[0]["envelope"] == primary_calls[0]
    assert len(local_calls) == 1


def test_assistant_failure_has_no_retry_metadata_when_local_is_unconfigured(monkeypatch):
    _configure_primary_failure(monkeypatch)
    monkeypatch.delenv("NOC_WEB_OLLAMA_BASE_URL", raising=False)

    response = TestClient(app).post(f"/api/shifts/{SHIFT}/assistant/questions", json={
        "shiftDate": SHIFT,
        "question": "What should I focus on?",
        "providerDisclosureAcknowledged": True,
    })

    assert response.status_code == 200
    assert "localRetry" not in response.json()


def test_assistant_retry_rejects_used_token_and_unsupported_provider(monkeypatch):
    _configure_primary_failure(monkeypatch)
    _configure_local(monkeypatch)
    client = TestClient(app)
    failed = client.post(f"/api/shifts/{SHIFT}/assistant/questions", json={
        "shiftDate": SHIFT,
        "question": "What should I focus on?",
        "providerDisclosureAcknowledged": True,
    })
    token = failed.json()["localRetry"]["retryToken"]

    first = client.post(
        f"/api/shifts/{SHIFT}/assistant/questions/local-retry",
        json={"retryToken": token, "confirmed": True},
    )
    second = client.post(
        f"/api/shifts/{SHIFT}/assistant/questions/local-retry",
        json={"retryToken": token, "confirmed": True},
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "retry-snapshot-used"
    unsupported = client.post(f"/api/shifts/{SHIFT}/assistant/questions", json={
        "shiftDate": SHIFT,
        "question": "What should I focus on?",
        "providerDisclosureAcknowledged": True,
        "provider": "unknown",
    })
    assert unsupported.status_code == 422


def test_investigation_retry_reuses_exact_previewed_package(
    investigation_workspace, monkeypatch,
):
    from backend.services import investigation_generation
    from backend.services.investigation_evidence import build_evidence_package
    from tests.support.investigation_ai import (
        INCIDENT_ID,
        NOTEBOOK_URL,
        SHIFT_DATE,
        evidence_bundle,
        fake_loader,
        fake_runtime,
        valid_output,
    )

    package = build_evidence_package(
        INCIDENT_ID,
        evidence_loader=fake_loader(evidence_bundle()),
    )
    loads = []

    def load(_incident_id, evidence_loader=None):
        loads.append(_incident_id)
        return package

    monkeypatch.setattr(investigation_generation, "build_evidence_package", load)
    primary = fake_runtime(error=CopilotProviderTimeout("primary timed out"))
    monkeypatch.setattr(
        investigation_generation,
        "_resolve_provider",
        lambda: primary,
    )
    monkeypatch.setenv("NOC_WEB_OLLAMA_BASE_URL", "http://ollama.lan:11434")
    monkeypatch.setenv("NOC_WEB_OLLAMA_MODEL", "qwen3:8b")
    local_calls = []

    def builder(configuration, *, system_prompt=None):
        def provider(envelope):
            local_calls.append(envelope)
            return valid_output(envelope["evidence"])

        return provider

    monkeypatch.setattr(ai_provider, "build_ollama_provider", builder)
    client = TestClient(app)
    preview = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/preview",
        json={
            "incidentId": INCIDENT_ID,
            "name": "Checkout Latency",
            "notebookUrl": NOTEBOOK_URL,
        },
    )
    assert preview.status_code == 200
    created = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations",
        json={
            "previewId": preview.json()["previewId"],
            "name": "Checkout Latency",
            "notebookUrl": NOTEBOOK_URL,
            "confirmed": True,
        },
    )
    assert created.status_code == 504, created.text
    local_retry = created.json()["detail"]["localRetry"]
    assert local_retry["available"] is True
    assert local_calls == []
    loaded_before_retry = len(loads)

    retried = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/local-retry",
        json={"retryToken": local_retry["retryToken"], "confirmed": True},
    )

    assert retried.status_code == 201
    assert len(loads) == loaded_before_retry
    assert len(local_calls) == 1
    assert local_calls[0]["evidence"]["incident"]["id"].endswith(INCIDENT_ID)
    record_dir = (
        investigation_workspace.noc_root
        / SHIFT_DATE
        / "investigations"
        / "checkout-latency"
    )
    provenance = json.loads(
        (record_dir / "evidence-provenance.json").read_text(encoding="utf-8")
    )
    assert provenance["provider"]["configuredProvider"] == "ollama"
    assert provenance["provider"]["model"] == "qwen3:8b"


def test_investigation_retry_requires_confirmation_and_single_use(
    investigation_workspace, monkeypatch,
):
    from backend.services import investigation_generation
    from backend.services.investigation_evidence import build_evidence_package
    from tests.support.investigation_ai import (
        INCIDENT_ID,
        NOTEBOOK_URL,
        SHIFT_DATE,
        evidence_bundle,
        fake_loader,
        fake_runtime,
        valid_output,
    )

    package = build_evidence_package(
        INCIDENT_ID,
        evidence_loader=fake_loader(evidence_bundle()),
    )
    monkeypatch.setattr(
        investigation_generation,
        "build_evidence_package",
        lambda _incident_id, evidence_loader=None: package,
    )
    monkeypatch.setattr(
        investigation_generation,
        "_resolve_provider",
        lambda: fake_runtime(error=CopilotProviderTimeout("primary timed out")),
    )
    monkeypatch.setenv("NOC_WEB_OLLAMA_BASE_URL", "http://ollama.lan:11434")
    monkeypatch.setattr(
        ai_provider,
        "build_ollama_provider",
        lambda configuration, *, system_prompt=None: (
            lambda envelope: valid_output(envelope["evidence"])
        ),
    )
    client = TestClient(app)
    preview = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/preview",
        json={
            "incidentId": INCIDENT_ID,
            "name": "Checkout Latency",
            "notebookUrl": NOTEBOOK_URL,
        },
    )
    failed = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations",
        json={
            "previewId": preview.json()["previewId"],
            "name": "Checkout Latency",
            "notebookUrl": NOTEBOOK_URL,
            "confirmed": True,
        },
    )
    assert failed.status_code == 504, failed.text
    token = failed.json()["detail"]["localRetry"]["retryToken"]

    unconfirmed = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/local-retry",
        json={"retryToken": token, "confirmed": False},
    )
    first = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/local-retry",
        json={"retryToken": token, "confirmed": True},
    )
    second = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/local-retry",
        json={"retryToken": token, "confirmed": True},
    )

    assert unconfirmed.status_code == 422
    assert unconfirmed.json()["detail"]["code"] == "retry-confirmation-required"
    assert first.status_code == 201, first.text
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "retry-snapshot-used"


def test_handover_retry_reuses_exact_evidence_and_records_ollama(noc_root, monkeypatch):
    from backend.services import handover
    from backend.services.handover_evidence import build_handover_evidence
    from tests.support.handover_ai import (
        SHIFT_DATE,
        fake_loader,
        fake_runtime,
        loaders,
        valid_advisory,
    )

    package = build_handover_evidence(SHIFT_DATE, **loaders())
    primary = fake_runtime(error=CopilotProviderTimeout("primary timed out"))
    monkeypatch.setenv("NOC_WEB_OLLAMA_BASE_URL", "http://ollama.lan:11434")
    monkeypatch.setenv("NOC_WEB_OLLAMA_MODEL", "qwen3:8b")
    local_calls = []

    def builder(configuration, *, system_prompt=None):
        def provider(envelope):
            local_calls.append(envelope)
            return valid_advisory(envelope["evidence"])

        return provider

    monkeypatch.setattr(ai_provider, "build_ollama_provider", builder)

    with pytest.raises(handover.HandoverGenerationError) as error:
        handover.generate_handover(
            SHIFT_DATE,
            evidence_loader=fake_loader(package),
            provider_runtime=primary,
        )

    assert error.value.code == "provider-timeout"
    retry = error.value.retry_metadata
    assert retry["available"] is True
    assert local_calls == []

    result = handover.retry_handover_generation(
        SHIFT_DATE,
        retry["retryToken"],
    )

    assert result["generationMode"] == "ai-advisory"
    assert len(local_calls) == 1
    assert local_calls[0] == primary.calls[0]
    handover_file = noc_root / SHIFT_DATE / "handover" / f"handover-{SHIFT_DATE}.md"
    provenance_file = noc_root / SHIFT_DATE / "handover" / "handover-provenance.json"
    assert handover_file.is_file()
    provenance = json.loads(provenance_file.read_text(encoding="utf-8"))
    assert provenance["provider"]["configuredProvider"] == "ollama"
    assert provenance["provider"]["model"] == "qwen3:8b"
    assert "[evidence:" not in handover_file.read_text(encoding="utf-8")


def test_handover_retry_token_is_single_use(noc_root, monkeypatch):
    from backend.services import handover
    from backend.services.handover_evidence import build_handover_evidence
    from tests.support.handover_ai import (
        SHIFT_DATE,
        fake_loader,
        fake_runtime,
        loaders,
        valid_advisory,
    )

    package = build_handover_evidence(SHIFT_DATE, **loaders())
    monkeypatch.setenv("NOC_WEB_OLLAMA_BASE_URL", "http://ollama.lan:11434")
    monkeypatch.setattr(
        ai_provider,
        "build_ollama_provider",
        lambda configuration, *, system_prompt=None: (
            lambda envelope: valid_advisory(envelope["evidence"])
        ),
    )
    with pytest.raises(handover.HandoverGenerationError) as error:
        handover.generate_handover(
            SHIFT_DATE,
            evidence_loader=fake_loader(package),
            provider_runtime=fake_runtime(
                error=CopilotProviderTimeout("primary timed out")
            ),
        )
    token = error.value.retry_metadata["retryToken"]

    handover.retry_handover_generation(SHIFT_DATE, token)
    with pytest.raises(handover.HandoverGenerationError) as used:
        handover.retry_handover_generation(SHIFT_DATE, token)

    assert used.value.code == "retry-snapshot-used"
