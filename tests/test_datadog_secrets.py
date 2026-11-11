import json
from datetime import datetime, timezone
from pathlib import Path

from backend.services import datadog_incidents
from backend.services.datadog_evidence import DatadogEvidenceFailure, get_incident_evidence
from backend.services.datadog_provider import (
    DatadogClient,
    DatadogConfiguration,
    DatadogResponse,
)


NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
TOKEN = "SENTINEL-DATADOG-TOKEN-DO-NOT-DISCLOSE"


def _client(transport):
    return DatadogClient(
        DatadogConfiguration(
            base_url="https://api.datadoghq.com",
            timeout_seconds=90,
            credential_present=True,
        ),
        TOKEN,
        transport=transport,
    )


def _empty_search():
    return {
        "data": {
            "type": "incidents_search_results",
            "attributes": {"incidents": [], "total": 0},
        }
    }


def _detail():
    return {
        "data": {
            "id": "incident-1",
            "type": "incidents",
            "attributes": {
                "title": "Sensitive incident",
                "state": "ACTIVE",
                "severity": "SEV-2",
                "created": "2026-11-10T10:00:00Z",
                "modified": "2026-11-10T10:10:00Z",
                "customer_impact_scope": "Bounded impact",
                "fields": {},
            },
        },
        "included": [],
    }


def test_sentinel_token_is_absent_from_success_output_logs_and_cache(
    tmp_path,
    fake_datadog_transport,
    caplog,
):
    cache_file = tmp_path / "incidents.json"
    fake_datadog_transport.add_json(_empty_search())

    snapshot = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: datadog_incidents.retrieve_active_incidents(
            client=_client(fake_datadog_transport)
        ),
        now=NOW,
    )

    assert TOKEN not in json.dumps(snapshot)
    assert TOKEN not in cache_file.read_text(encoding="utf-8")
    assert TOKEN not in caplog.text
    assert TOKEN not in repr(_client(fake_datadog_transport))


def test_sentinel_token_is_absent_from_evidence_output(
    fake_datadog_transport,
):
    fake_datadog_transport.add_json(_detail())

    bundle = get_incident_evidence(
        "incident-1",
        client=_client(fake_datadog_transport),
    )

    assert TOKEN not in json.dumps(bundle)
    assert TOKEN not in str(bundle)


def test_sentinel_token_in_error_body_is_not_disclosed(
    tmp_path,
    fake_datadog_transport,
    caplog,
):
    cache_file = tmp_path / "incidents.json"
    previous = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: {"incidents": []},
        now=NOW,
    )
    fake_datadog_transport.add_response(
        DatadogResponse(
            401,
            json.dumps({"error": TOKEN, "message": f"bad {TOKEN}"}).encode(),
            "application/json",
        )
    )

    failed = datadog_incidents.refresh_incident_cache(
        cache_file,
        provider=lambda: datadog_incidents.retrieve_active_incidents(
            client=_client(fake_datadog_transport)
        ),
        now=NOW,
    )

    assert failed["error"] == "provider-unavailable"
    assert failed["incidents"] == previous["incidents"]
    assert TOKEN not in json.dumps(failed)
    assert TOKEN not in cache_file.read_text(encoding="utf-8")
    assert TOKEN not in caplog.text


def test_sentinel_token_is_absent_from_failure_exceptions(
    fake_datadog_transport,
):
    fake_datadog_transport.add_response(
        DatadogResponse(
            500,
            json.dumps({"error": TOKEN}).encode(),
            "application/json",
        )
    )

    try:
        get_incident_evidence(
            "incident-1",
            client=_client(fake_datadog_transport),
        )
    except DatadogEvidenceFailure as error:
        assert TOKEN not in str(error)
        assert TOKEN not in repr(error)
    else:
        raise AssertionError("expected a controlled provider failure")


def test_sentinel_token_is_absent_from_created_files(
    tmp_path,
    fake_datadog_transport,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    fake_datadog_transport.add_json(_detail())

    get_incident_evidence(
        "incident-1",
        client=_client(fake_datadog_transport),
    )

    for path in Path(tmp_path).rglob("*"):
        if path.is_file():
            assert TOKEN not in path.read_text(encoding="utf-8", errors="ignore")


def test_investigation_generation_modules_do_not_embed_credential_settings():
    root = Path(__file__).resolve().parents[1]
    for relative in (
        "backend/services/investigation_generation.py",
        "backend/services/investigation_evidence.py",
        "backend/services/investigation_ai.py",
        "backend/services/investigation_preview_store.py",
    ):
        source = (root / relative).read_text(encoding="utf-8")
        for sentinel in (
            "DEEPSEEK_API_KEY",
            "NOC_WEB_DEEPSEEK_API_KEY",
            "DD_ACCESS_TOKEN",
            "NOC_WEB_DATADOG_ACCESS_TOKEN",
        ):
            assert sentinel not in source
