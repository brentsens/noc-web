from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_dashboard_and_investigations_use_one_shared_incident_renderer():
    renderer = (FRONTEND / "js" / "active-incidents.js").read_text(
        encoding="utf-8"
    )
    dashboard = (FRONTEND / "index.html").read_text(encoding="utf-8")
    investigations = (FRONTEND / "investigations.html").read_text(
        encoding="utf-8"
    )

    assert dashboard.count('from "./js/active-incidents.js"') == 1
    assert investigations.count('from "./js/active-incidents.js"') == 1
    assert 'id="active-datadog-incidents"' in dashboard
    assert 'id="active-datadog-incidents"' in investigations
    assert "getDatadogIncidents()" in renderer
    assert "refreshDatadogIncidents()" in renderer
    assert "View Incidents →" in renderer
    assert "{ showViewIncidents: true }" in dashboard
    assert "textContent" in renderer
    assert "datadoghq.com" in renderer
    assert "fetch(" not in renderer
    assert "XMLHttpRequest" not in renderer
    assert "freshness-${snapshot.freshness}" in renderer
    assert 'snapshot.freshness.toUpperCase()' in renderer
    assert "Waiting for the first successful incident refresh." in renderer
    assert investigations.index('id="active-datadog-incidents"') < investigations.index(
        'id="investigation-list"'
    )


def test_backend_retrieval_does_not_add_direct_datadog_api_or_sdk():
    service = (ROOT / "backend" / "services" / "datadog_incidents.py").read_text(
        encoding="utf-8"
    )
    assert "datadog(search_datadog_incidents)" in service
    assert "requests." not in service
    assert "httpx." not in service
    assert "@datadog/datadog-api-client" not in service
    assert "datadoghq.com/api/" not in service


def test_incident_handoff_prefills_title_only_and_keeps_confirmation_gates():
    renderer = (FRONTEND / "js" / "active-incidents.js").read_text(
        encoding="utf-8"
    )
    investigations = (FRONTEND / "investigations.html").read_text(
        encoding="utf-8"
    )

    assert '"noc-web:incident-title-handoff"' in renderer
    assert 'window.location.href = "investigations.html"' in renderer
    assert "createInvestigation" not in renderer
    assert 'getItem(\n                "noc-web:incident-title-handoff"' in investigations
    assert "createNameInput.value = incidentTitleHint.trim()" in investigations
    assert "notebookUrlInput.value = incidentTitleHint" not in investigations
    assert "previewInvestigation(" in investigations
    assert "createInvestigation(" in investigations
    assert "if (!window.confirm(confirmation))" in investigations
    assert "confirmed: true" in investigations or "pendingPreview.notebookUrl,\n                    true" in investigations


def test_failed_incident_get_preserves_the_last_successful_snapshot():
    renderer = (FRONTEND / "js" / "active-incidents.js").read_text(
        encoding="utf-8"
    )

    assert "if (latestSnapshot?.lastSuccessfulAt)" in renderer
    assert "          ...latestSnapshot," in renderer
    assert 'freshness: "stale"' in renderer
    assert 'error: "request-failed"' in renderer
    assert 'freshness: "unavailable"' in renderer


def test_active_incident_card_displays_incident_id_as_text():
    renderer = (FRONTEND / "js" / "active-incidents.js").read_text(
        encoding="utf-8"
    )

    assert "ID ${incident.id}" in renderer
    assert "element.textContent = text" in renderer


def test_datadog_state_is_rendered_exactly_and_stable_incidents_keep_actions():
    renderer = (FRONTEND / "js" / "active-incidents.js").read_text(
        encoding="utf-8"
    )
    investigations = (FRONTEND / "investigations.html").read_text(
        encoding="utf-8"
    )
    incident_card = renderer.split("function renderIncident", 1)[1].split(
        "function render(",
        1,
    )[0]

    assert 'node("span", "incident-state", incident.state)' in renderer
    assert "incident.state.toUpperCase()" not in renderer
    assert 'node("h2", "", "Datadog Incidents")' in renderer
    assert 'aria-label="Datadog Incidents"' in investigations
    assert "View in Datadog ↗" in incident_card
    assert "Create Investigation" in incident_card
    assert "if (allowCreateInvestigation)" in incident_card
    assert "incident.state ===" not in incident_card


def test_current_incident_count_and_empty_state_include_stable_incidents():
    renderer = (FRONTEND / "js" / "active-incidents.js").read_text(
        encoding="utf-8"
    )

    assert "`${snapshot.count} Current Datadog Incident" in renderer
    assert "No current Datadog incidents." in renderer
    assert "for (const incident of snapshot.incidents)" in renderer
    assert "`${snapshot.count} Active`" not in renderer
    assert "No active Datadog incidents." not in renderer


def test_refresh_control_uses_container_delegation_across_replacements():
    renderer = (FRONTEND / "js" / "active-incidents.js").read_text(
        encoding="utf-8"
    )

    assert 'refreshButton.dataset.action = "refresh-incidents"' in renderer
    assert 'container.addEventListener("click", handleRefreshClick)' in renderer
    assert 'container.removeEventListener("click", handleRefreshClick)' in renderer
    assert 'refreshButton.addEventListener("click"' not in renderer
