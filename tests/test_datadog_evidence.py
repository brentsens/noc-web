from pathlib import Path

import pytest

from backend.services.datadog_evidence import (
    DatadogEvidenceFailure,
    extract_incident_references,
    extract_notebook_references,
    get_incident_evidence,
    get_monitor_evidence,
    get_notebook_evidence,
    normalize_notebook,
)
from backend.services.datadog_provider import DatadogProviderTimeout, DatadogResponse


TOKEN = "test-sentinel-datadog-token"


def _client(transport):
    from backend.services.datadog_provider import DatadogClient, DatadogConfiguration

    return DatadogClient(
        DatadogConfiguration(
            base_url="https://api.datadoghq.com",
            timeout_seconds=90,
            credential_present=True,
        ),
        TOKEN,
        transport=transport,
    )


def _incident_detail(*, fields=None, included=None):
    attributes = {
        "title": "Checkout latency",
        "state": "ACTIVE",
        "severity": "SEV-2",
        "created": "2026-11-10T10:00:00Z",
        "modified": "2026-11-10T10:12:00Z",
        "resolved": None,
        "detected": "2026-11-10T09:58:00Z",
        "customer_impact_scope": "Elevated checkout errors in us-east-1.",
        "customer_impacted": True,
        "fields": fields or {},
    }
    return {
        "data": {
            "id": "incident-1",
            "type": "incidents",
            "attributes": attributes,
        },
        "included": included or [],
    }


def _notebook(notebook_id="123", *, cells=None, name="Checkout runbook"):
    return {
        "data": {
            "id": notebook_id,
            "type": "notebooks",
            "attributes": {
                "name": name,
                "cells": cells
                if cells is not None
                else [
                    {
                        "attributes": {
                            "definition": {
                                "type": "markdown",
                                "text": "# Checkout runbook",
                            }
                        }
                    },
                    {
                        "attributes": {
                            "definition": {
                                "type": "timeseries",
                                "title": "Latency",
                                "description": "p95 latency",
                                "time": {
                                    "from": "2026-11-10T09:00:00Z",
                                    "to": "2026-11-10T10:00:00Z",
                                },
                                "requests": [
                                    {"q": "avg:checkout.latency{*}"}
                                ],
                            }
                        }
                    },
                ],
                "created": "2026-11-10T09:00:00Z",
                "modified": "2026-11-10T09:30:00Z",
            },
        }
    }


def _monitor(monitor_id="456", *, assets=None):
    return {
        "id": int(monitor_id),
        "name": "Checkout p95 latency",
        "type": "metric alert",
        "query": "avg(last_5m):avg:checkout.latency{*} > 100",
        "options": {"thresholds": {"critical": 100, "warning": 80}},
        "tags": ["service:checkout", "env:prod"],
        "overall_state": "Alert",
        "message": "Checkout latency is high.",
        "assets": assets
        if assets is not None
        else [
            {
                "resource_type": "notebook",
                "resource_key": "789",
                "url": "https://app.datadoghq.com/notebook/789/checkout",
            }
        ],
        "created": "2026-11-01T09:00:00Z",
        "modified": "2026-11-10T09:30:00Z",
    }


def test_incident_evidence_preserves_relationships_and_sources(
    fake_datadog_transport,
):
    fields = {
        "runbook": "https://app.datadoghq.com/notebook/123/checkout",
        "monitor": "monitor:456",
    }
    fake_datadog_transport.add_json(_incident_detail(fields=fields))
    fake_datadog_transport.add_json(_monitor())
    fake_datadog_transport.add_json(_notebook("123"))
    fake_datadog_transport.add_json(_notebook("789", name="Monitor runbook"))

    bundle = get_incident_evidence(
        "incident-1",
        client=_client(fake_datadog_transport),
    )

    assert bundle["status"] == "complete"
    assert bundle["error"] is None
    assert bundle["incident"]["id"] == "incident-1"
    assert bundle["incident"]["sourceUrl"] == (
        "https://app.datadoghq.com/incidents/incident-1"
    )
    assert [entry["reference"]["id"] for entry in bundle["notebooks"]] == [
        "123",
        "789",
    ]
    assert [entry["reference"]["id"] for entry in bundle["monitors"]] == ["456"]
    assert bundle["relationships"]["notebookIds"] == ["123", "789"]
    assert bundle["relationships"]["monitorIds"] == ["456"]
    assert bundle["relationships"]["sources"]["notebook:789"] == "monitor_asset"
    assert all(
        reference["status"] == "available"
        for reference in bundle["incident"]["references"]
    )
    assert TOKEN not in str(bundle)


def test_unavailable_reference_marks_bundle_partial_and_keeps_incident(
    fake_datadog_transport,
):
    fields = {"monitor": "monitor:456"}
    fake_datadog_transport.add_json(_incident_detail(fields=fields))
    fake_datadog_transport.add_response(
        DatadogResponse(404, b"{}", "application/json")
    )

    bundle = get_incident_evidence(
        "incident-1",
        client=_client(fake_datadog_transport),
    )

    assert bundle["status"] == "partial"
    assert bundle["incident"]["id"] == "incident-1"
    assert bundle["monitors"][0]["status"] == "unavailable"
    assert bundle["monitors"][0]["error"] == "not-found"
    assert bundle["incident"]["unavailableReferences"][0]["id"] == "456"


def test_incident_detail_malformed_fails_closed(fake_datadog_transport):
    fake_datadog_transport.add_json({"data": {"id": "incident-1"}})

    with pytest.raises(DatadogEvidenceFailure) as error:
        get_incident_evidence(
            "incident-1",
            client=_client(fake_datadog_transport),
        )

    assert error.value.code == "invalid-response"


@pytest.mark.parametrize("incident_type", [None, "notebooks", "monitors"])
def test_incident_detail_wrong_type_fails_closed(
    fake_datadog_transport,
    incident_type,
):
    payload = _incident_detail()
    if incident_type is None:
        payload["data"].pop("type")
    else:
        payload["data"]["type"] = incident_type
    fake_datadog_transport.add_json(payload)

    with pytest.raises(DatadogEvidenceFailure) as error:
        get_incident_evidence(
            "incident-1",
            client=_client(fake_datadog_transport),
        )

    assert error.value.code == "invalid-response"


def test_notebook_evidence_preserves_markdown_queries_and_time_ranges(
    fake_datadog_transport,
):
    fake_datadog_transport.add_json(_notebook("123"))

    evidence = get_notebook_evidence(
        "123",
        client=_client(fake_datadog_transport),
    )

    assert evidence["id"] == "123"
    assert evidence["title"] == "Checkout runbook"
    assert evidence["sourceUrl"] == "https://app.datadoghq.com/notebook/123"
    assert evidence["cells"][0]["type"] == "markdown"
    assert evidence["cells"][0]["markdown"] == "# Checkout runbook"
    assert evidence["cells"][1]["type"] == "timeseries"
    assert evidence["cells"][1]["timeRange"] == {
        "from": "2026-11-10T09:00:00Z",
        "to": "2026-11-10T10:00:00Z",
    }
    assert evidence["cells"][1]["queries"] == ["avg:checkout.latency{*}"]
    assert evidence["omittedCellTypes"] == {}


def test_notebook_omits_unsupported_cells_explicitly(fake_datadog_transport):
    cells = [
        {"attributes": {"definition": {"type": "markdown", "text": "Run"}}},
        {"attributes": {"definition": {"type": "topology"}}},
        {"attributes": {"definition": {"type": "topology"}}},
    ]
    fake_datadog_transport.add_json(_notebook("123", cells=cells))

    evidence = get_notebook_evidence(
        "123",
        client=_client(fake_datadog_transport),
    )

    assert [cell["type"] for cell in evidence["cells"]] == ["markdown"]
    assert evidence["omittedCellTypes"] == {"topology": 2}
    assert "topology" not in str(evidence["cells"])


@pytest.mark.parametrize("cell_type", ["x" * 65, "bad\x01type"])
def test_notebook_unsupported_cell_type_is_bounded_and_sanitized(
    fake_datadog_transport,
    cell_type,
):
    cells = [
        {"attributes": {"definition": {"type": "markdown", "text": "Run"}}},
        {"attributes": {"definition": {"type": cell_type}}},
    ]
    fake_datadog_transport.add_json(_notebook("123", cells=cells))

    with pytest.raises(DatadogEvidenceFailure) as error:
        get_notebook_evidence("123", client=_client(fake_datadog_transport))

    assert error.value.code == "invalid-response"


def test_notebook_without_supported_cells_or_over_bound_is_rejected(
    fake_datadog_transport,
):
    fake_datadog_transport.add_json(
        _notebook(
            "123",
            cells=[{"attributes": {"definition": {"type": "topology"}}}],
        )
    )
    with pytest.raises(DatadogEvidenceFailure) as error:
        get_notebook_evidence("123", client=_client(fake_datadog_transport))
    assert error.value.code == "invalid-response"

    too_many = [
        {"attributes": {"definition": {"type": "markdown", "text": "x"}}}
        for _ in range(201)
    ]
    fake_datadog_transport.add_json(_notebook("123", cells=too_many))
    with pytest.raises(DatadogEvidenceFailure) as error:
        get_notebook_evidence("123", client=_client(fake_datadog_transport))
    assert error.value.code == "invalid-response"


def test_notebook_query_definition_overflow_fails_closed(
    fake_datadog_transport,
):
    cells = [
        {
            "attributes": {
                "definition": {
                    "type": "timeseries",
                    "requests": [
                        {"q": f"avg:checkout.metric_{index}{{*}}"}
                        for index in range(21)
                    ],
                }
            }
        }
    ]
    fake_datadog_transport.add_json(_notebook("123", cells=cells))

    with pytest.raises(DatadogEvidenceFailure) as error:
        get_notebook_evidence("123", client=_client(fake_datadog_transport))

    assert error.value.code == "invalid-response"


def test_monitor_evidence_exposes_required_fields(fake_datadog_transport):
    fake_datadog_transport.add_json(_monitor())

    evidence = get_monitor_evidence(
        "456",
        client=_client(fake_datadog_transport),
    )

    assert evidence["id"] == "456"
    assert evidence["name"] == "Checkout p95 latency"
    assert evidence["type"] == "metric alert"
    assert evidence["query"] == "avg(last_5m):avg:checkout.latency{*} > 100"
    assert evidence["thresholds"] == {"critical": 100, "warning": 80}
    assert evidence["tags"] == ["service:checkout", "env:prod"]
    assert evidence["state"] == "Alert"
    assert evidence["message"] == "Checkout latency is high."
    assert evidence["sourceUrl"] == "https://app.datadoghq.com/monitors/456"
    assert evidence["assets"][0]["resourceType"] == "notebook"


def test_more_than_ten_references_of_one_kind_is_rejected(
    fake_datadog_transport,
):
    fields = {
        f"runbook-{index}": f"notebook:{100 + index}"
        for index in range(11)
    }
    fake_datadog_transport.add_json(_incident_detail(fields=fields))

    with pytest.raises(DatadogEvidenceFailure) as error:
        get_incident_evidence(
            "incident-1",
            client=_client(fake_datadog_transport),
        )

    assert error.value.code == "invalid-response"


def test_evidence_requests_do_not_write_cache_files(
    fake_datadog_transport,
    tmp_path,
):
    fake_datadog_transport.add_json(_notebook("123"))
    before = set(tmp_path.iterdir())

    get_notebook_evidence(
        "123",
        client=_client(fake_datadog_transport),
    )

    assert set(tmp_path.iterdir()) == before
    assert not (tmp_path / ".datadog-active-incidents.json").exists()


def test_monitor_malformed_fields_are_rejected(fake_datadog_transport):
    payload = _monitor()
    payload["tags"] = ["ok", 3]
    fake_datadog_transport.add_json(payload)

    with pytest.raises(DatadogEvidenceFailure) as error:
        get_monitor_evidence("456", client=_client(fake_datadog_transport))

    assert error.value.code == "invalid-response"


@pytest.mark.parametrize("options", ["bad", [], 5])
def test_monitor_malformed_options_are_rejected(
    fake_datadog_transport,
    options,
):
    payload = _monitor()
    payload["options"] = options
    fake_datadog_transport.add_json(payload)

    with pytest.raises(DatadogEvidenceFailure) as error:
        get_monitor_evidence("456", client=_client(fake_datadog_transport))

    assert error.value.code == "invalid-response"


def test_notebook_id_mismatch_is_rejected(fake_datadog_transport):
    fake_datadog_transport.add_json(_notebook("999"))

    with pytest.raises(DatadogEvidenceFailure) as error:
        get_notebook_evidence("123", client=_client(fake_datadog_transport))

    assert error.value.code == "invalid-response"


@pytest.mark.parametrize("notebook_type", [None, "incidents", "monitors"])
def test_notebook_wrong_type_is_rejected(fake_datadog_transport, notebook_type):
    payload = _notebook("123")
    if notebook_type is None:
        payload["data"].pop("type")
    else:
        payload["data"]["type"] = notebook_type
    fake_datadog_transport.add_json(payload)

    with pytest.raises(DatadogEvidenceFailure) as error:
        get_notebook_evidence("123", client=_client(fake_datadog_transport))

    assert error.value.code == "invalid-response"


@pytest.mark.parametrize(
    "fields",
    [
        {"teams": {"type": "autocomplete", "value": None}},
        [{"name": "teams", "type": "autocomplete", "value": None}],
    ],
)
def test_null_autocomplete_incident_field_is_treated_as_absent(
    fake_datadog_transport,
    fields,
):
    fake_datadog_transport.add_json(_incident_detail(fields=fields))

    bundle = get_incident_evidence(
        "incident-1",
        client=_client(fake_datadog_transport),
    )

    assert bundle["status"] == "complete"
    assert bundle["incident"]["fields"] == {}


def test_long_summary_incident_field_and_references_are_preserved(
    fake_datadog_transport,
):
    summary = (
        "Checkout latency remained elevated throughout the incident. " * 80
    ).strip()
    assert len(summary) > 500
    fields = {
        "summary": summary,
        "runbook": "https://app.datadoghq.com/notebook/123/checkout",
        "monitor": "https://app.datadoghq.com/monitors/456",
    }
    fake_datadog_transport.add_json(_incident_detail(fields=fields))
    fake_datadog_transport.add_json(_monitor(assets=[]))
    fake_datadog_transport.add_json(_notebook("123"))

    bundle = get_incident_evidence(
        "incident-1",
        client=_client(fake_datadog_transport),
    )

    assert bundle["status"] == "complete"
    assert bundle["incident"]["fields"]["summary"] == summary
    assert [entry["reference"]["id"] for entry in bundle["notebooks"]] == ["123"]
    assert [entry["reference"]["id"] for entry in bundle["monitors"]] == ["456"]


def _narrative_references(text, *, app_base_url="https://app.datadoghq.com"):
    return extract_incident_references(
        _incident_detail(fields={"summary": text}),
        app_base_url=app_base_url,
    )


def test_relative_notebook_path_in_narrative_is_extracted():
    references = _narrative_references("Notebook: /notebook/16295624")

    assert references == [
        {
            "kind": "notebook",
            "id": "16295624",
            "source": "incident_field",
            "sourceUrl": "https://app.datadoghq.com/notebook/16295624",
            "status": "available",
            "error": None,
        }
    ]


def test_relative_monitor_path_in_markdown_link_is_extracted():
    references = _narrative_references("Investigate [monitor](/monitors/150243517) now.")

    assert [reference["kind"] for reference in references] == ["monitor"]
    assert references[0]["id"] == "150243517"
    assert references[0]["source"] == "incident_field"
    assert references[0]["sourceUrl"] == (
        "https://app.datadoghq.com/monitors/150243517"
    )


def test_multiple_relative_references_in_long_narrative_are_extracted():
    narrative = (
        "Checkout latency remained elevated. " * 80
        + "See /notebook/16295624 and [monitor](/monitors/150243517). "
        + "Also review /notebook/16295625."
    )
    assert len(narrative) > 2048

    references = _narrative_references(narrative)

    assert [
        (reference["kind"], reference["id"]) for reference in references
    ] == [
        ("notebook", "16295624"),
        ("monitor", "150243517"),
        ("notebook", "16295625"),
    ]
    assert all(
        reference["source"] == "incident_field"
        for reference in references
    )


def test_duplicate_relative_references_are_deduplicated():
    narrative = (
        "/notebook/16295624 then /notebook/16295624 again "
        "and [the same notebook](/notebook/16295624)."
    )

    references = _narrative_references(narrative)

    assert [reference["id"] for reference in references] == ["16295624"]


@pytest.mark.parametrize(
    "text",
    [
        "/notebook/0",
        "/notebook/016295624",
        "/notebook/16295624abc",
        "/notebook/16295624/extra",
        "/notebook/16295624?ref=other",
        "/notebook/16295624#section",
        "/notebook/16295624.5",
        "/notebook/16295624%2e",
        "/monitors/not-a-number",
        "/monitors/150243517abc",
    ],
)
def test_malformed_relative_reference_ids_are_ignored(text):
    assert _narrative_references(text) == []


@pytest.mark.parametrize(
    "text",
    [
        "/dashboards/123",
        "/notebooks/123",
        "foo/notebook/123",
        "//evil.example/notebook/123",
        "https://evil.example/notebook/123",
        "https://app.datadoghq.com/dashboards/123",
    ],
)
def test_unrelated_relative_paths_are_ignored(text):
    assert _narrative_references(text) == []


def test_existing_absolute_and_kind_id_references_are_still_supported():
    payload = _incident_detail(
        fields={
            "notebook": "notebook:123",
            "monitor": "https://app.datadoghq.com/monitors/456",
        }
    )

    references = extract_incident_references(
        payload,
        app_base_url="https://app.datadoghq.com",
    )

    assert [
        (reference["kind"], reference["id"]) for reference in references
    ] == [("notebook", "123"), ("monitor", "456")]


def test_relative_narrative_references_are_retrieved_with_provenance(
    fake_datadog_transport,
):
    fields = {
        "summary": (
            "Notebook: /notebook/123\n"
            "Monitor: [checkout](/monitors/456)"
        )
    }
    fake_datadog_transport.add_json(_incident_detail(fields=fields))
    fake_datadog_transport.add_json(_monitor(assets=[]))
    fake_datadog_transport.add_json(_notebook("123"))

    bundle = get_incident_evidence(
        "incident-1",
        client=_client(fake_datadog_transport),
    )

    assert bundle["status"] == "complete"
    assert [entry["reference"]["id"] for entry in bundle["notebooks"]] == ["123"]
    assert [entry["reference"]["id"] for entry in bundle["monitors"]] == ["456"]
    assert bundle["relationships"]["sources"] == {
        "notebook:123": "incident_field",
        "monitor:456": "incident_field",
    }
    source_urls = {
        reference["kind"]: reference["sourceUrl"]
        for reference in bundle["incident"]["references"]
    }
    assert source_urls == {
        "notebook": "https://app.datadoghq.com/notebook/123",
        "monitor": "https://app.datadoghq.com/monitors/456",
    }


def _normalized_notebook_with_monitor_links(notebook_id="16295624"):
    return normalize_notebook(
        _notebook(
            notebook_id,
            cells=[
                {
                    "attributes": {
                        "definition": {
                            "type": "markdown",
                            "text": (
                                "Monitor: /monitors/150243517\n"
                                "See [second](/monitors/253825030).\n"
                                "Duplicate /monitors/150243517\n"
                                "Malformed /monitors/0 /monitors/abc "
                                "/monitors/150243517abc /monitors/150243517/extra\n"
                                "Unrelated /notebook/999 and /dashboards/123"
                            ),
                        }
                    }
                },
                {
                    "attributes": {
                        "definition": {
                            "type": "timeseries",
                            "title": "Monitor /monitors/253825030",
                            "description": "See /monitors/150243517",
                            "requests": [{"q": "avg:checkout.latency{*}"}],
                        }
                    }
                },
            ],
        ),
        notebook_id=notebook_id,
        app_base_url="https://app.datadoghq.com",
    )


def test_notebook_monitor_references_are_extracted_from_supported_content():
    notebook = _normalized_notebook_with_monitor_links()

    references = extract_notebook_references(
        notebook,
        app_base_url="https://app.datadoghq.com",
    )

    assert [
        (reference["kind"], reference["id"], reference["source"])
        for reference in references
    ] == [
        ("monitor", "150243517", "notebook"),
        ("monitor", "253825030", "notebook"),
    ]
    assert [reference["sourceUrl"] for reference in references] == [
        "https://app.datadoghq.com/monitors/150243517",
        "https://app.datadoghq.com/monitors/253825030",
    ]


def test_notebook_monitor_references_ignore_unsupported_cell_content():
    payload = _notebook(
        "16295624",
        cells=[
            {"attributes": {"definition": {"type": "markdown", "text": "Runbook"}}},
            {
                "attributes": {
                    "definition": {
                        "type": "topology",
                        "config": {"link": "/monitors/150243517"},
                    }
                }
            },
        ],
    )

    assert (
        extract_notebook_references(
            payload,
            app_base_url="https://app.datadoghq.com",
        )
        == []
    )


def test_notebook_monitor_references_are_retrieved_into_relationships(
    fake_datadog_transport,
):
    fields = {"summary": "Notebook: /notebook/16295624"}
    fake_datadog_transport.add_json(_incident_detail(fields=fields))
    fake_datadog_transport.add_json(
        _notebook(
            "16295624",
            cells=[
                {
                    "attributes": {
                        "definition": {
                            "type": "markdown",
                            "text": (
                                "Monitor: /monitors/150243517\n"
                                "See [second](/monitors/253825030).\n"
                                "Duplicate /monitors/150243517\n"
                                "Malformed /monitors/0 /monitors/abc"
                            ),
                        }
                    }
                }
            ],
        )
    )
    fake_datadog_transport.add_json(_monitor("150243517", assets=[]))
    fake_datadog_transport.add_json(_monitor("253825030", assets=[]))

    bundle = get_incident_evidence(
        "incident-1",
        client=_client(fake_datadog_transport),
    )

    assert bundle["status"] == "complete"
    assert bundle["relationships"]["notebookIds"] == ["16295624"]
    assert bundle["relationships"]["monitorIds"] == ["150243517", "253825030"]
    assert bundle["relationships"]["sources"]["monitor:150243517"] == "notebook"
    assert bundle["relationships"]["sources"]["monitor:253825030"] == "notebook"
    assert [entry["reference"]["id"] for entry in bundle["monitors"]] == [
        "150243517",
        "253825030",
    ]
    assert all(
        entry["status"] == "available" for entry in bundle["monitors"]
    )
    assert len(fake_datadog_transport.calls) == 4
    assert all(
        call["method"] == "GET" for call in fake_datadog_transport.calls
    )


def test_notebook_monitor_references_deduplicate_with_incident_references(
    fake_datadog_transport,
):
    fields = {
        "monitor": "monitor:150243517",
        "summary": "Notebook: /notebook/16295624",
    }
    fake_datadog_transport.add_json(_incident_detail(fields=fields))
    fake_datadog_transport.add_json(_monitor("150243517", assets=[]))
    fake_datadog_transport.add_json(
        _notebook(
            "16295624",
            cells=[
                {
                    "attributes": {
                        "definition": {
                            "type": "markdown",
                            "text": (
                                "/monitors/150243517 and /monitors/253825030"
                            ),
                        }
                    }
                }
            ],
        )
    )
    fake_datadog_transport.add_json(_monitor("253825030", assets=[]))

    bundle = get_incident_evidence(
        "incident-1",
        client=_client(fake_datadog_transport),
    )

    assert bundle["relationships"]["monitorIds"] == ["150243517", "253825030"]
    assert bundle["relationships"]["sources"]["monitor:150243517"] == (
        "incident_field"
    )
    assert bundle["relationships"]["sources"]["monitor:253825030"] == "notebook"
    assert [entry["reference"]["id"] for entry in bundle["monitors"]] == [
        "150243517",
        "253825030",
    ]
    assert len(fake_datadog_transport.calls) == 4
    assert all(
        call["method"] == "GET" for call in fake_datadog_transport.calls
    )


def test_more_than_ten_notebook_monitor_references_fails_closed(
    fake_datadog_transport,
):
    notebook_id = "16295624"
    links = " ".join(
        f"/monitors/{150243517 + index}" for index in range(11)
    )
    fields = {"summary": f"Notebook: /notebook/{notebook_id}"}
    fake_datadog_transport.add_json(_incident_detail(fields=fields))
    fake_datadog_transport.add_json(
        _notebook(
            notebook_id,
            cells=[
                {
                    "attributes": {
                        "definition": {"type": "markdown", "text": links}
                    }
                }
            ],
        )
    )

    with pytest.raises(DatadogEvidenceFailure) as error:
        get_incident_evidence(
            "incident-1",
            client=_client(fake_datadog_transport),
        )

    assert error.value.code == "invalid-response"


@pytest.mark.parametrize(
    "fields",
    [
        {"summary": "x" * 10_001},
        {"custom": "x" * 501},
        {"summary": {"type": "text", "value": {"nested": "value"}}},
        [{"name": "summary", "type": "text"}],
        [{"name": "summary", "type": "text", "value": ["x"] * 21}],
    ],
)
def test_malformed_or_oversized_incident_fields_still_fail_closed(
    fake_datadog_transport,
    fields,
):
    fake_datadog_transport.add_json(_incident_detail(fields=fields))

    with pytest.raises(DatadogEvidenceFailure) as error:
        get_incident_evidence(
            "incident-1",
            client=_client(fake_datadog_transport),
        )

    assert error.value.code == "invalid-response"


def test_incident_detail_preserves_optional_fields_and_source_url(
    fake_datadog_transport,
):
    fake_datadog_transport.add_json(
        _incident_detail(fields={"service": "checkout"})
    )

    bundle = get_incident_evidence(
        "incident-1",
        client=_client(fake_datadog_transport),
    )

    detail = bundle["incident"]
    assert detail["severity"] == "SEV-2"
    assert detail["createdAt"] == "2026-11-10T10:00:00Z"
    assert detail["updatedAt"] == "2026-11-10T10:12:00Z"
    assert detail["resolvedAt"] is None
    assert detail["detectedAt"] == "2026-11-10T09:58:00Z"
    assert detail["impactScope"] == (
        "Elevated checkout errors in us-east-1."
    )
    assert detail["customerImpacted"] is True
    assert detail["fields"] == {"service": "checkout"}
    assert detail["sourceUrl"] == (
        "https://app.datadoghq.com/incidents/incident-1"
    )
    assert bundle["status"] == "complete"


def test_incident_link_attachments_are_discovered(fake_datadog_transport):
    included = [
        {
            "attributes": {
                "attachment": {
                    "attachment_type": "link",
                    "documentUrl": "https://app.datadoghq.com/monitors/456",
                }
            }
        },
        {
            "attributes": {
                "attachment": {
                    "attachment_type": "link",
                    "documentUrl": (
                        "https://app.datadoghq.com/notebook/789/runbook"
                    ),
                }
            }
        },
    ]
    fake_datadog_transport.add_json(_incident_detail(included=included))
    fake_datadog_transport.add_json(_monitor("456", assets=[]))
    fake_datadog_transport.add_json(_notebook("789"))

    bundle = get_incident_evidence(
        "incident-1",
        client=_client(fake_datadog_transport),
    )

    assert bundle["relationships"]["monitorIds"] == ["456"]
    assert bundle["relationships"]["notebookIds"] == ["789"]
    assert bundle["relationships"]["sources"] == {
        "monitor:456": "incident_attachment",
        "notebook:789": "incident_attachment",
    }
    assert bundle["status"] == "complete"


def test_notebook_metadata_is_normalized(fake_datadog_transport):
    payload = _notebook("123")
    payload["data"]["attributes"]["status"] = "published"
    fake_datadog_transport.add_json(payload)

    evidence = get_notebook_evidence(
        "123",
        client=_client(fake_datadog_transport),
    )

    assert evidence["metadata"] == {
        "created": "2026-11-10T09:00:00Z",
        "modified": "2026-11-10T09:30:00Z",
        "status": "published",
    }


@pytest.mark.parametrize("field", ["thresholds", "tags", "assets"])
def test_monitor_over_bound_collections_are_rejected(
    fake_datadog_transport,
    field,
):
    payload = _monitor()
    if field == "thresholds":
        payload["options"]["thresholds"] = {
            f"level_{index}": index for index in range(21)
        }
    elif field == "tags":
        payload["tags"] = [f"tag:{index}" for index in range(101)]
    else:
        payload["assets"] = [
            {"resource_type": "notebook", "resource_key": str(700 + index)}
            for index in range(21)
        ]
    fake_datadog_transport.add_json(payload)

    with pytest.raises(DatadogEvidenceFailure) as error:
        get_monitor_evidence("456", client=_client(fake_datadog_transport))

    assert error.value.code == "invalid-response"


@pytest.mark.parametrize(
    ("response", "expected_error"),
    [
        (DatadogProviderTimeout("timeout"), "timeout"),
        (DatadogResponse(403, b"{}", "application/json"), "forbidden"),
        (DatadogResponse(200, b"[]", "application/json"), "invalid-response"),
    ],
)
def test_reference_level_failures_are_reported_as_partial(
    fake_datadog_transport,
    response,
    expected_error,
):
    fields = {"monitor": "monitor:456"}
    fake_datadog_transport.add_json(_incident_detail(fields=fields))
    if isinstance(response, BaseException):
        fake_datadog_transport.add_error(response)
    else:
        fake_datadog_transport.add_response(response)

    bundle = get_incident_evidence(
        "incident-1",
        client=_client(fake_datadog_transport),
    )

    assert bundle["status"] == "partial"
    assert bundle["monitors"][0]["status"] == "unavailable"
    assert bundle["monitors"][0]["error"] == expected_error
    assert bundle["incident"]["unavailableReferences"][0]["error"] == (
        expected_error
    )

