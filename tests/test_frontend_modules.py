import base64
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
    modules = (
        FRONTEND / "js" / "api.js",
        FRONTEND / "js" / "workflow-context.js",
        FRONTEND / "js" / "resources.js",
    )
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


def test_resource_inventory_has_exact_groups_and_urls():
    module = FRONTEND / "js" / "resources.js"
    script = """
      import { readFileSync } from "node:fs";
      const source = readFileSync(process.argv[1], "utf8");
      const { RESOURCE_GROUPS } = await import(
        `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
      );
      console.log(JSON.stringify(RESOURCE_GROUPS));
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, str(module)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [
        {
            "title": "SES ENVIRONMENTS",
            "resources": [
                {
                    "name": "USPRI SES",
                    "url": "https://app.uspri.sesami.io/aaa/login?targetUrl=https://app.uspri.sesami.io/",
                    "environment": "production",
                },
                {
                    "name": "EU SES",
                    "url": "https://app.sesami.io/aaa/login?targetUrl=https://app.sesami.io/",
                    "environment": "production",
                },
                {
                    "name": "MEXPRI SES",
                    "url": "https://app.mexpri.sesami.io/",
                    "environment": "production",
                },
                {
                    "name": "DEMO SES",
                    "url": "https://app.demo.sesami.io/aaa/login?targetUrl=https://app.demo.sesami.io/",
                    "environment": "demo",
                },
            ],
        },
        {
            "title": "TICKETS & SUPPORT",
            "resources": [
                {
                    "name": "NOC Jira",
                    "url": "https://sesamidevel.atlassian.net/issues/?filter=22992",
                    "dashboardQuickLink": True,
                },
                {
                    "name": "Salesforce",
                    "url": "https://sesami.lightning.force.com/lightning/o/Case/list?filterName=NOC_SES_Case",
                    "dashboardQuickLink": True,
                },
                {
                    "name": "DevOps Ticket Portal",
                    "url": "https://sesamidevel.atlassian.net/servicedesk/customer/portal/199",
                },
            ],
        },
        {
            "title": "DOCUMENTATION",
            "resources": [
                {
                    "name": "NOC Confluence",
                    "url": "https://sesamidevel.atlassian.net/wiki/spaces/NOC/overview",
                },
                {
                    "name": "SES Confluence",
                    "url": "https://sesami-io.atlassian.net/wiki/home?cloudId=8986e79a-6c2a-4e0d-bb65-4a57e0f68db9&source=peopleMenu",
                },
                {
                    "name": "Atlassian Home",
                    "url": "https://home.atlassian.com/o/87e5c9f6-4c36-46da-a68f-a39ba95b7c5a/?cloudId=8986e79a-6c2a-4e0d-bb65-4a57e0f68db9",
                },
            ],
        },
        {
            "title": "OBSERVABILITY",
            "resources": [
                {
                    "name": "Datadog",
                    "url": "https://app.datadoghq.com/apm/home?env=%2A&graphType=service_map&shouldShowLegend=true&traceQuery=&view=services",
                    "dashboardQuickLink": True,
                },
            ],
        },
    ]


def test_dashboard_quick_links_use_shared_resource_inventory():
    module = FRONTEND / "js" / "resources.js"
    dashboard = (FRONTEND / "index.html").read_text(encoding="utf-8")
    module_script = MODULE_SCRIPT_PATTERN.findall(dashboard)[0]
    render_start = module_script.index("const dashboardQuickLinks =")
    render_end = module_script.index("const dashboardDate =", render_start)
    render_block = module_script[render_start:render_end]
    script = """
      import { readFileSync } from "node:fs";
      const source = readFileSync(process.argv[1], "utf8");
      const { RESOURCE_GROUPS } = await import(
        `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
      );
      class Element {
        constructor(tagName) {
          this.tagName = tagName;
          this.children = [];
          this.attributes = {};
          this.textContent = "";
        }
        append(...children) { this.children.push(...children); }
        appendChild(child) { this.children.push(child); }
        setAttribute(name, value) { this.attributes[name] = value; }
      }
      const root = new Element("nav");
      globalThis.document = {
        querySelector: () => root,
        createElement: tagName => new Element(tagName)
      };
      __RENDER_BLOCK__
      console.log(JSON.stringify({
        links: root.children.map(link => ({
          name: link.children[0].textContent,
          href: link.href,
          target: link.target,
          rel: link.rel,
          ariaLabel: link.attributes["aria-label"],
          indicator: link.children[1].textContent
        })),
        expectedUrls: quickLinkResources.map(resource => resource.url)
      }));
    """
    script = script.replace("__RENDER_BLOCK__", render_block)
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, str(module)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    rendered = json.loads(result.stdout)
    links = rendered["links"]
    assert [resource["name"] for resource in links] == [
        "NOC Jira",
        "Salesforce",
        "Datadog",
    ]
    assert [resource["href"] for resource in links] == rendered["expectedUrls"]
    assert all(
        link["target"] == "_blank"
        and link["rel"] == "noopener noreferrer"
        and link["indicator"] == "↗"
        and link["ariaLabel"] == f'{link["name"]}, opens in a new tab'
        and "shift=" not in link["href"]
        for link in links
    )
    assert 'id="dashboard-quick-links"' in dashboard
    assert 'import { RESOURCE_GROUPS } from "./js/resources.js";' in dashboard
    assert "dashboardQuickLink" in dashboard
    assert 'link.target = "_blank"' in dashboard
    assert 'link.rel = "noopener noreferrer"' in dashboard
    assert 'id="resources-directory-link"' in dashboard
    assert "https://" not in dashboard
    component_styles = (FRONTEND / "css" / "components.css").read_text(
        encoding="utf-8"
    )
    layout_styles = (FRONTEND / "css" / "layout.css").read_text(
        encoding="utf-8"
    )
    assert ".dashboard-quick-links {" in component_styles
    assert ".dashboard-resource-link {" in component_styles
    assert ".dashboard-actions-grid {" in layout_styles


def test_resources_page_uses_external_link_safety_and_shared_shell():
    page = (FRONTEND / "resources.html").read_text(encoding="utf-8")
    styles = (FRONTEND / "css" / "components.css").read_text(encoding="utf-8")
    assert 'href="css/theme.css"' in page
    assert 'href="css/layout.css"' in page
    assert 'href="css/components.css"' in page
    assert 'class="app-shell"' in page
    assert 'class="resource-groups"' in page
    assert 'link.target = "_blank"' in page
    assert 'link.rel = "noopener noreferrer"' in page
    assert 'indicator.textContent = "↗"' in page
    assert 'resource-card-demo' in page
    assert "preserveSelectedShiftNavigation()" in page
    assert "fetch(" not in page
    assert "targetUrl" not in page
    assert ".resource-card-demo {" in styles
    assert re.search(
        r"@media \(max-width: 650px\)\s*\{\s*"
        r"\.resource-grid\s*\{\s*grid-template-columns:\s*1fr;",
        styles,
    )

    html_pages = list(FRONTEND.glob("*.html"))
    assert all(
        "https://" not in page_file.read_text(encoding="utf-8")
        for page_file in html_pages
    )
    for page_file in html_pages:
        content = page_file.read_text(encoding="utf-8")
        if '<aside class="sidebar">' in content:
            sidebar = re.search(
                r'<aside class="sidebar">(.*?)</aside>',
                content,
                re.DOTALL,
            )
            assert sidebar is not None
            assert sidebar.group(1).count('href="resources.html"') == 1, page_file.name


def test_resources_page_renders_safe_external_links_in_dom_smoke():
    page = (FRONTEND / "resources.html").read_text(encoding="utf-8")
    script = MODULE_SCRIPT_PATTERN.findall(page)[0]
    resources_source = (FRONTEND / "js" / "resources.js").read_text(encoding="utf-8")
    resources_url = (
        "data:text/javascript;base64,"
        + base64.b64encode(resources_source.encode()).decode()
    )
    script = script.replace(
        'import { RESOURCE_GROUPS } from "./js/resources.js";',
        f"const {{ RESOURCE_GROUPS }} = await import({json.dumps(resources_url)});",
    )
    script = script.replace(
        'import { preserveSelectedShiftNavigation } from "./js/workflow-context.js";',
        "const preserveSelectedShiftNavigation = () => {};",
    )
    script += """
      const walk = element => [
        element,
        ...element.children.flatMap(walk)
      ];
      const anchors = walk(root)
        .filter(element => element.tagName === "A")
        .map(link => ({
          name: link.children[0].children[0].textContent,
          href: link.href,
          target: link.target,
          rel: link.rel,
          className: link.className,
          indicator: link.children[1].textContent
        }));
      const groupTitles = walk(root)
        .filter(element => element.tagName === "H2")
        .map(element => element.textContent);
      const disclosures = walk(root)
        .filter(element => element.tagName === "DETAILS")
        .map(element => ({
          open: element.open,
          summaryTag: element.children[0]?.tagName
        }));
      console.log(JSON.stringify({ anchors, groupTitles, disclosures }));
    """
    setup = """
      class Element {
        constructor(tagName) {
          this.tagName = tagName.toUpperCase();
          this.children = [];
          this.attributes = {};
          this.className = "";
          this.textContent = "";
        }
        append(...children) { this.children.push(...children); }
        setAttribute(name, value) { this.attributes[name] = value; }
      }
      const root = new Element("div");
      globalThis.document = {
        querySelector: () => root,
        createElement: tagName => new Element(tagName)
      };
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", setup + script],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    rendered = json.loads(result.stdout)
    anchors = rendered["anchors"]
    assert len(anchors) == 11
    assert rendered["groupTitles"] == [
        "SES ENVIRONMENTS",
        "TICKETS & SUPPORT",
        "DOCUMENTATION",
        "OBSERVABILITY",
    ]
    assert len(rendered["disclosures"]) == 4
    assert all(
        disclosure == {"open": True, "summaryTag": "SUMMARY"}
        for disclosure in rendered["disclosures"]
    )
    assert all(
        anchor["target"] == "_blank"
        and anchor["rel"] == "noopener noreferrer"
        and anchor["indicator"] == "↗"
        and "shift=" not in anchor["href"]
        for anchor in anchors
    )
    demo = next(anchor for anchor in anchors if anchor["name"] == "DEMO SES")
    assert "resource-card-demo" in demo["className"]


def test_resources_navigation_preserves_only_valid_selected_shift():
    module = FRONTEND / "js" / "workflow-context.js"
    resources_module = FRONTEND / "js" / "resources.js"
    script = """
      import { readFileSync } from "node:fs";
      const source = readFileSync(process.argv[1], "utf8");
      const context = await import(
        `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
      );
      const resourceSource = readFileSync(process.argv[2], "utf8");
      const { RESOURCE_GROUPS } = await import(
        `data:text/javascript;base64,${Buffer.from(resourceSource).toString("base64")}`
      );
      const externalLinks = RESOURCE_GROUPS
        .flatMap(group => group.resources)
        .filter(resource => resource.dashboardQuickLink)
        .map(resource => resource.url);
      const links = ["index.html", "resources.html", ...externalLinks]
        .map(href => ({
          value: href,
          getAttribute() { return this.value; },
          set href(value) { this.value = value; }
        }));
      globalThis.window = {
        location: { href: "https://noc-web.invalid/resources.html?shift=2026-10-30" }
      };
      globalThis.document = { querySelectorAll: () => links };
      context.preserveSelectedShiftNavigation();
      console.log(JSON.stringify({
        links: links.map(link => link.value),
        externalLinks
      }));
    """
    result = subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            script,
            str(module),
            str(resources_module),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    context_result = json.loads(result.stdout)
    assert context_result["links"] == [
        "index.html?shift=2026-10-30",
        "resources.html?shift=2026-10-30",
        *context_result["externalLinks"],
    ]


def test_resource_inventory_is_not_added_to_assistant_context():
    resource_source = (FRONTEND / "js" / "resources.js").read_text(
        encoding="utf-8"
    )
    assistant_context = (
        FRONTEND.parent / "backend" / "services" / "assistant_context.py"
    ).read_text(encoding="utf-8")
    assistant_page = (FRONTEND / "assistant.html").read_text(encoding="utf-8")
    resource_urls = re.findall(r'url:\s*"([^"]+)"', resource_source)

    assert "RESOURCE_GROUPS" not in assistant_context
    assert "resources.js" not in assistant_page
    assert all(url not in assistant_context for url in resource_urls)


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
        providerStatus: "not-invoked",
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


def test_assistant_api_accepts_stale_citations_and_not_invoked_provenance():
    module = FRONTEND / "js" / "api.js"
    script = """
      import { readFileSync } from "node:fs";
      const source = readFileSync(process.argv[1], "utf8");
      const api = await import(
        `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
      );
      const shiftDate = "2026-10-30";
      const response = {
        shiftDate,
        status: "complete",
        provider: "github-copilot-cli",
        providerInvoked: true,
        providerStatus: "success",
        facts: [{
          text: "The stale Jira cache may not reflect current ticket status.",
          evidenceIds: ["jira-cache"]
        }],
        reviewedFindings: [],
        aiObservations: [],
        recommendations: [],
        evidence: [{
          id: "jira-cache",
          kind: "jira-cache",
          provenance: "noc-web",
          availability: "stale",
          freshness: "stale",
          reference: null
        }],
        limitations: ["Jira cache (jira-cache) is stale."]
      };
      globalThis.fetch = async () => ({ ok: true, json: async () => response });
      await api.askAssistant(shiftDate, "Which tracked tickets need attention?", true);
      response.status = "limited";
      response.providerInvoked = false;
      response.providerStatus = "not-invoked";
      response.facts = [];
      await api.askAssistant(shiftDate, "What was the last action taken today?", true);
      response.status = "complete";
      let invalidNotInvokedRejected = false;
      try {
        await api.askAssistant(shiftDate, "What was the last action taken today?", true);
      } catch {
        invalidNotInvokedRejected = true;
      }
      console.log(JSON.stringify({ invalidNotInvokedRejected }));
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, str(module)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"invalidNotInvokedRejected": True}


def test_assistant_pages_render_provider_provenance_and_empty_success_notice():
    assistant = (FRONTEND / "assistant.html").read_text(encoding="utf-8")
    assert "response.providerInvoked" in assistant
    assert "response.providerStatus" in assistant
    assert '"AI ENGINE", "GitHub Copilot CLI"' in assistant
    assert '"PROVIDER STATUS"' in assistant
    assert '"not-invoked": "NOT INVOKED"' in assistant
    assert "assistant-provider-status" in assistant
    assert "no AI-generated observations or recommendations" in assistant

    ai_actions = (FRONTEND / "ai-actions.html").read_text(encoding="utf-8")
    assert "response.providerInvoked" in ai_actions
    assert "response.providerStatus" in ai_actions
    assert "AI Engine: GitHub Copilot CLI" in ai_actions
    assert "Provider Invoked:" in ai_actions
    assert "Provider Status:" in ai_actions
    assert '"not-invoked": "NOT INVOKED"' in ai_actions
    assert "no AI-generated observations or recommendations" in ai_actions


def test_assistant_uses_shared_sesami_shell_and_responsive_components():
    page = (FRONTEND / "assistant.html").read_text(encoding="utf-8")
    components = (FRONTEND / "css" / "components.css").read_text(encoding="utf-8")
    workflow_context = (FRONTEND / "js" / "workflow-context.js").read_text(encoding="utf-8")

    assert 'href="css/theme.css"' in page
    assert 'href="css/layout.css"' in page
    assert 'href="css/components.css"' in page
    assert 'class="app-shell"' in page
    assert 'class="sidebar"' in page
    assert 'class="topbar"' in page
    assert 'class="content"' in page
    assert 'class="panel assistant-interaction"' in page
    assert 'class="form-control note-textarea assistant-question-input"' in page
    assert 'class="button primary assistant-submit"' in page
    assert ".workflow-bar {" in components
    assert 'bar.className = "workflow-bar"' in workflow_context
    assert "initializeWorkflow({" in page
    assert 'requireExplicitShift: true' in page
    assert "assistant-provider-provenance" in components
    assert "@media (max-width: 650px)" in components


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
                "./js/resources.js",
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


def test_investigation_creation_uses_preview_and_confirmed_api_contract():
    page = (FRONTEND / "investigations.html").read_text(encoding="utf-8")
    api = (FRONTEND / "js" / "api.js").read_text(encoding="utf-8")

    assert "+ Create from Datadog Notebook" in page
    assert "FINAL Datadog Notebook URL" in page
    assert "Create Investigation" in page
    assert "await previewInvestigation(" in page
    assert "await createInvestigation(" in page
    assert "window.confirm(confirmation)" in page
    assert "This does not modify evidence, Datadog, or Jira." in page
    assert "export function previewInvestigation(" in api
    assert "export function createInvestigation(" in api
    assert "fetch(pendingPreview.notebookUrl" not in page
    end_shift = (FRONTEND / "end-shift.html").read_text(encoding="utf-8")
    assert "preflight.investigations.needsReview" in end_shift
    assert "excluded from handover" in end_shift
