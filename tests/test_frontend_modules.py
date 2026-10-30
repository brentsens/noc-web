import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit


FRONTEND = Path(__file__).parents[1] / "frontend"
MODULE_SCRIPT_PATTERN = re.compile(
    r'<script\s+type=["\']module["\']\s*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
NAMED_IMPORT_PATTERN = re.compile(
    r'import\s*\{(?P<names>[^}]+)\}\s*from\s*["\'](?P<path>[^"\']+)["\']',
)
NAMED_EXPORT_PATTERN = re.compile(
    r'export\s+(?:async\s+)?function\s+(?P<function>[A-Za-z_$][\w$]*)'
    r'|export\s*\{(?P<names>[^}]+)\}',
)


def _names(clause: str) -> set[str]:
    return {
        name.strip().split(" as ")[0].strip()
        for name in clause.split(",")
        if name.strip()
    }


def _exports(module: Path) -> set[str]:
    exports = set()
    for match in NAMED_EXPORT_PATTERN.finditer(module.read_text(encoding="utf-8")):
        if match.group("function"):
            exports.add(match.group("function"))
        else:
            exports.update(_names(match.group("names")))
    return exports


def test_browser_module_sources_have_valid_es_module_syntax():
    modules = (FRONTEND / "js" / "api.js", FRONTEND / "js" / "workflow-context.js")
    for module in modules:
        result = subprocess.run(
            ["node", "--check", "--input-type=module"],
            input=module.read_text(encoding="utf-8"),
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr


def test_assistant_context_requires_explicit_shift_without_changing_other_workflows():
    module = FRONTEND / "js" / "workflow-context.js"
    script = """
      import { readFileSync } from "node:fs";
      globalThis.window = {
        location: { href: "https://noc-web.invalid/assistant.html" },
        history: { replaceState() {} }
      };
      const source = readFileSync(process.argv[1], "utf8");
      const contextModule = await import(
        `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
      );
      const assistant = contextModule.getWorkflowContext({ requireExplicitShift: true });
      const existing = contextModule.getWorkflowContext();
      console.log(JSON.stringify({ assistant, existing }));
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, str(module)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    contexts = json.loads(result.stdout)
    assert contexts["assistant"]["valid"] is False
    assert contexts["assistant"]["shift"] is None
    assert contexts["existing"]["valid"] is True
    assert contexts["existing"]["normalized"] is True


def test_assistant_api_rejects_malformed_and_shift_changing_routes():
    module = FRONTEND / "js" / "api.js"
    script = """
      import { readFileSync } from "node:fs";
      const source = readFileSync(process.argv[1], "utf8");
      const api = await import(
        `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
      );
      const shiftDate = "2026-10-29";
      const response = {
        shiftDate,
        status: "limited",
        provider: "github-copilot-cli",
        providerInvoked: false,
        providerStatus: "unavailable",
        facts: [],
        reviewedFindings: [],
        aiObservations: [],
        recommendations: [{
          text: "Review before acting.",
          evidenceIds: [],
          route: {
            label: "Open Tickets",
            href: `tickets.html?shift=${shiftDate}`,
            requiresConfirmation: true
          }
        }],
        evidence: [],
        limitations: ["Nothing was changed."]
      };
      globalThis.fetch = async () => ({ ok: true, json: async () => response });
      await api.askAssistant(shiftDate, "Review this shift.", true);
      response.recommendations[0].route.href = "tickets.html?shift=2026-10-28";
      let shiftRouteRejected = false;
      try {
        await api.askAssistant(shiftDate, "Review this shift.", true);
      } catch {
        shiftRouteRejected = true;
      }
      response.recommendations[0].route.href = `tickets.html?shift=${shiftDate}`;
      response.recommendations[0].route.requiresConfirmation = false;
      let confirmationRejected = false;
      try {
        await api.askAssistant(shiftDate, "Review this shift.", true);
      } catch {
        confirmationRejected = true;
      }
      response.recommendations[0].route.requiresConfirmation = true;
      response.providerStatus = "success";
      let successWithoutInvocationRejected = false;
      try {
        await api.askAssistant(shiftDate, "Review this shift.", true);
      } catch {
        successWithoutInvocationRejected = true;
      }
      response.providerStatus = "unavailable";
      response.provider = "unapproved-provider";
      let unknownProviderRejected = false;
      try {
        await api.askAssistant(shiftDate, "Review this shift.", true);
      } catch {
        unknownProviderRejected = true;
      }
      console.log(JSON.stringify({
        shiftRouteRejected,
        confirmationRejected,
        successWithoutInvocationRejected,
        unknownProviderRejected
      }));
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, str(module)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    outcomes = json.loads(result.stdout)
    assert outcomes == {
        "shiftRouteRejected": True,
        "confirmationRejected": True,
        "successWithoutInvocationRejected": True,
        "unknownProviderRejected": True,
    }


def test_assistant_pages_render_provider_provenance_and_empty_success_notice():
    for filename in ("assistant.html", "ai-actions.html"):
        page = (FRONTEND / filename).read_text(encoding="utf-8")
        assert "response.providerInvoked" in page
        assert "response.providerStatus" in page
        assert "AI Engine: GitHub Copilot CLI" in page
        assert "Provider Invoked:" in page
        assert "Provider Status:" in page
        assert "no AI-generated observations or recommendations" in page


def test_html_module_scripts_have_valid_es_module_syntax_and_resolved_named_imports():
    checked_pages = 0
    for page in FRONTEND.glob("*.html"):
        scripts = MODULE_SCRIPT_PATTERN.findall(page.read_text(encoding="utf-8"))
        imports = [
            match
            for script in scripts
            for match in NAMED_IMPORT_PATTERN.finditer(script)
            if urlsplit(match.group("path")).path in {
                "./js/api.js",
                "./js/workflow-context.js",
            }
        ]
        if not imports:
            continue

        checked_pages += 1
        for script in scripts:
            result = subprocess.run(
                ["node", "--check", "--input-type=module"],
                input=script,
                text=True,
                capture_output=True,
                check=False,
            )
            assert result.returncode == 0, f"{page}: {result.stderr}"

        for imported in imports:
            module = (page.parent / urlsplit(imported.group("path")).path).resolve()
            missing = _names(imported.group("names")) - _exports(module)
            assert not missing, f"{page}: {module.name} does not export {sorted(missing)}"

    assert checked_pages > 0


def test_ai_analysis_cards_are_wired_to_bounded_assistant_requests():
    page = FRONTEND / "ai-actions.html"
    content = page.read_text(encoding="utf-8")
    scripts = MODULE_SCRIPT_PATTERN.findall(content)
    script = "\n".join(scripts)
    card_actions = set(
        re.findall(r'<button\b[^>]*data-action="([^"]+)"', content)
    )
    assert card_actions == {"analysis", "summary", "followups", "handover"}
    assert re.search(
        r'import\s*\{[^}]*\brunAssistantAction\s+as\s+requestAssistantAction\b[^}]*\}\s*from\s*["\']\./js/api\.js["\']',
        script,
        re.DOTALL,
    )
    assert re.search(
        r'button\.addEventListener\(\s*"click",\s*\(\)\s*=>\s*\{\s*runAssistantAction\(button\)',
        script,
        re.DOTALL,
    )
    assert re.search(
        r"await requestAssistantAction\(\s*workflowContext\.shift,\s*action,\s*true\s*\)",
        script,
        re.DOTALL,
    )
    assert re.search(
        r'initializeWorkflow\(\s*\{\s*step:\s*"assistant",\s*dateInput:\s*aiDate',
        script,
        re.DOTALL,
    )
    assert "actionRequestActive = true" in script
    assert "actionCards.forEach(card => {" in script
    assert "finally {" in script
    assert "updateActionAvailability();" in script
    assert 'id="ai-action-provider-disclosure"' in content
    assert "actionAcknowledgement.checked" in script
    assert "await loadReports(workflowContext.shift)" in script
    assert "actionResult.reportSaveWarning" in script
    assert 'id="ai-action-report-save-warning"' in content


def test_assistant_action_api_uses_fixed_action_and_validates_report_response():
    module = FRONTEND / "js" / "api.js"
    script = """
      import { readFileSync } from "node:fs";
      const source = readFileSync(process.argv[1], "utf8");
      const api = await import(
        `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
      );
      const shiftDate = "2026-10-29";
      const assistant = {
        shiftDate,
        status: "complete",
        provider: "github-copilot-cli",
        providerInvoked: true,
        providerStatus: "success",
        facts: [],
        reviewedFindings: [],
        aiObservations: [],
        recommendations: [],
        evidence: [],
        limitations: []
      };
      const report = {
        name: "ai-shift-summary-20261029T000000000000Z-a1b2c3d4.md",
        title: "Summarize Current Shift",
        file: "ai-shift-summary-20261029T000000000000Z-a1b2c3d4.md",
        available: true
      };
      let request;
      globalThis.fetch = async (url, options) => {
        request = { url, options };
        return {
          ok: true,
          json: async () => ({ assistant, report, reportSaveWarning: null })
        };
      };
      await api.runAssistantAction(shiftDate, "summary", true);
      let invalidActionRejected = false;
      try {
        await api.runAssistantAction(shiftDate, "freeform", true);
      } catch {
        invalidActionRejected = true;
      }
      report.name = "../outside.md";
      let invalidReportRejected = false;
      try {
        await api.runAssistantAction(shiftDate, "summary", true);
      } catch {
        invalidReportRejected = true;
      }
      console.log(JSON.stringify({
        url: request.url,
        method: request.options.method,
        body: JSON.parse(request.options.body),
        invalidActionRejected,
        invalidReportRejected
      }));
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, str(module)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    outcome = json.loads(result.stdout)
    assert outcome == {
        "url": "/api/shifts/2026-10-29/assistant/actions/summary",
        "method": "POST",
        "body": {"providerDisclosureAcknowledged": True},
        "invalidActionRejected": True,
        "invalidReportRejected": True,
    }


def test_investigations_route_requires_datadog_provenance_in_frontend_validation():
    module = FRONTEND / "js" / "api.js"
    script = """
      import { readFileSync } from "node:fs";
      const source = readFileSync(process.argv[1], "utf8");
      const api = await import(
        `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
      );
      const shiftDate = "2026-10-29";
      const response = {
        shiftDate,
        status: "complete",
        provider: "github-copilot-cli",
        providerInvoked: true,
        providerStatus: "success",
        facts: [],
        reviewedFindings: [],
        aiObservations: [],
        recommendations: [{
          text: "Review this correlation.",
          evidenceIds: ["jira-cache"],
          route: {
            label: "Open Investigations",
            href: `investigations.html?shift=${shiftDate}`,
            requiresConfirmation: true
          }
        }],
        evidence: [{
          id: "jira-cache",
          kind: "jira-cache",
          provenance: "noc-web",
          availability: "available",
          reference: null,
          freshness: "current"
        }],
        limitations: []
      };
      globalThis.fetch = async () => ({ ok: true, json: async () => response });
      let jiraOnlyRejected = false;
      try {
        await api.askAssistant(shiftDate, "Review ticket correlation.", true);
      } catch {
        jiraOnlyRejected = true;
      }
      response.recommendations[0].evidenceIds = ["investigation:monitor"];
      response.evidence.push({
        id: "investigation:monitor",
        kind: "investigation",
        provenance: "noc-inv",
        availability: "available",
        reference: null
      });
      await api.askAssistant(shiftDate, "Review investigation.", true);
      console.log(JSON.stringify({ jiraOnlyRejected }));
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, str(module)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"jiraOnlyRejected": True}
