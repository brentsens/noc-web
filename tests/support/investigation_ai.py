from __future__ import annotations

from types import SimpleNamespace
from typing import Any


INCIDENT_ID = "aadf7955-1945-4ce6-b6ca-41e7fa734a78"
NOTEBOOK_ID = "16295624"
MONITOR_ID = "150243517"
SECOND_MONITOR_ID = "253825030"
SHIFT_DATE = "2099-12-31"
NOTEBOOK_URL = "https://app.datadoghq.com/notebook/16295624/runbook"


def incident_detail(
    *,
    incident_id: str = INCIDENT_ID,
    state: str = "ACTIVE",
    title: str = "Checkout latency elevated",
) -> dict[str, Any]:
    return {
        "id": incident_id,
        "title": title,
        "state": state,
        "severity": "SEV-2",
        "createdAt": "2026-11-10T22:40:00Z",
        "updatedAt": "2026-11-10T22:45:00Z",
        "resolvedAt": None,
        "detectedAt": "2026-11-10T22:39:00Z",
        "impactScope": "Elevated checkout errors in us-east-1.",
        "customerImpacted": True,
        "fields": {"service": "checkout"},
        "sourceUrl": f"https://app.datadoghq.com/incidents/{incident_id}",
    }


def notebook_evidence(
    *,
    notebook_id: str = NOTEBOOK_ID,
    title: str = "Checkout latency runbook",
    markdown: str = "Checkout runbook. See monitor:150243517.",
) -> dict[str, Any]:
    return {
        "id": notebook_id,
        "title": title,
        "sourceUrl": f"https://app.datadoghq.com/notebook/{notebook_id}",
        "cells": [
            {"index": 0, "type": "markdown", "markdown": markdown},
            {
                "index": 1,
                "type": "timeseries",
                "title": "Latency",
                "description": "Checkout latency",
                "timeRange": {"from": 1, "to": 2},
                "queries": ["avg:checkout.latency{*}"],
            },
        ],
        "omittedCellTypes": {},
        "metadata": {
            "created": "2026-11-10T22:00:00Z",
            "modified": "2026-11-10T22:30:00Z",
        },
    }


def monitor_evidence(
    *,
    monitor_id: str = MONITOR_ID,
    name: str = "Checkout error rate",
    query: str = "avg(last_5m):sum:checkout.errors{*}.as_count() > 10",
) -> dict[str, Any]:
    return {
        "id": monitor_id,
        "name": name,
        "type": "metric alert",
        "query": query,
        "thresholds": {"critical": 10},
        "tags": ["service:checkout"],
        "state": "Alert",
        "message": "Checkout errors are elevated.",
        "sourceUrl": f"https://app.datadoghq.com/monitors/{monitor_id}",
    }


def reference(kind: str, identifier: str, *, source: str) -> dict[str, Any]:
    path = {
        "incident": "incidents",
        "notebook": "notebook",
        "monitor": "monitors",
    }[kind]
    return {
        "kind": kind,
        "id": identifier,
        "source": source,
        "sourceUrl": f"https://app.datadoghq.com/{path}/{identifier}",
        "status": "available",
        "error": None,
    }


def evidence_bundle(
    *,
    incident_id: str = INCIDENT_ID,
    state: str = "ACTIVE",
    include_notebook: bool = True,
    include_monitor: bool = True,
    unavailable_notebook: bool = False,
    unavailable_monitor: bool = False,
    notebook_markdown: str | None = None,
    monitor_query: str | None = None,
) -> dict[str, Any]:
    notebooks = []
    monitors = []
    notebook_refs = []
    monitor_refs = []
    unavailable = []
    if include_notebook:
        notebook_ref = reference("notebook", NOTEBOOK_ID, source="incident_field")
        if unavailable_notebook:
            notebook_ref.update({"status": "unavailable", "error": "not-found"})
            notebooks.append({
                "reference": notebook_ref,
                "status": "unavailable",
                "error": "not-found",
                "evidence": None,
            })
            unavailable.append(notebook_ref)
        else:
            notebooks.append({
                "reference": notebook_ref,
                "status": "available",
                "error": None,
                "evidence": notebook_evidence(
                    markdown=notebook_markdown
                    or "Checkout runbook. See monitor:150243517.",
                ),
            })
        notebook_refs.append(notebook_ref)
    if include_monitor:
        monitor_ref = reference("monitor", MONITOR_ID, source="notebook")
        if unavailable_monitor:
            monitor_ref.update({"status": "unavailable", "error": "timeout"})
            monitors.append({
                "reference": monitor_ref,
                "status": "unavailable",
                "error": "timeout",
                "evidence": None,
            })
            unavailable.append(monitor_ref)
        else:
            monitors.append({
                "reference": monitor_ref,
                "status": "available",
                "error": None,
                "evidence": monitor_evidence(
                    query=monitor_query
                    or "avg(last_5m):sum:checkout.errors{*}.as_count() > 10",
                ),
            })
        monitor_refs.append(monitor_ref)
    return {
        "incident": incident_detail(incident_id=incident_id, state=state),
        "notebooks": notebooks,
        "monitors": monitors,
        "relationships": {
            "incidentId": incident_id,
            "notebookIds": [NOTEBOOK_ID] if include_notebook else [],
            "monitorIds": [MONITOR_ID] if include_monitor else [],
            "sources": {
                f"{item['kind']}:{item['id']}": item["source"]
                for item in [*notebook_refs, *monitor_refs]
            },
        },
        "status": "partial" if unavailable else "complete",
        "error": None,
    }


def valid_output(package: dict[str, Any]) -> dict[str, list[str]]:
    incident = package["incident"]["id"]
    notebooks = package.get("notebooks", [])
    monitors = package.get("monitors", [])
    notebook = notebooks[0]["id"] if notebooks else incident
    monitor = monitors[0]["id"] if monitors else incident
    return {
        "summary": [f"Checkout latency is elevated ({incident})."],
        "confirmedFindings": [f"Notebook evidence shows elevated latency ({notebook})."],
        "currentStatus": [f"Monitor remains alerting ({monitor})."],
        "nextActions": [f"Review monitor thresholds ({monitor})."],
        "handoverSummary": [f"Continue monitoring the incident ({incident})."],
    }


def fake_runtime(
    *,
    identifier: str = "deepseek-api",
    model: str = "deepseek-flash",
    readiness: str = "ready",
    output: dict[str, Any] | None = None,
    error: BaseException | None = None,
    calls: list[dict[str, Any]] | None = None,
):
    if calls is None:
        calls = []

    def provider(envelope):
        calls.append(envelope)
        if error is not None:
            raise error
        if output is not None:
            return output
        package = envelope.get("evidence", {})
        return valid_output(package)

    return SimpleNamespace(
        identifier=identifier,
        provider=provider,
        readiness={
            "configuredProvider": identifier,
            "readiness": readiness,
            "label": "DeepSeek API" if identifier == "deepseek-api" else "Provider",
            "model": model,
        },
        calls=calls,
    )


def fake_loader(bundle: dict[str, Any]):
    def load(_incident_id: str):
        return bundle
    return load


class Clock:
    def __init__(self, value: float = 1000.0):
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds
