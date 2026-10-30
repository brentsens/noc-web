# Implementation Plan: NOC Resources Experience

**Branch**: `007-add-noc-resources` | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/007-add-noc-resources/spec.md`

## Summary

Deliver the operator-facing Resources directory and Dashboard Quick Links as a static frontend
enhancement. Reuse the existing SESAMI application shell, shared styles, selected-shift navigation,
and centralized resource catalog. The catalog is the sole source for the 11 exact external
destinations and identifies the three external Dashboard shortcuts; Dashboard also has one
internal Resources link. All four resource groups are collapsible and expanded on initial desktop
view. No backend endpoint, external integration, persistent state, or operational write is
introduced.

## Technical Context

**Language/Version**: HTML5, CSS, browser-native JavaScript ES modules; existing Python 3 backend is unchanged

**Primary Dependencies**: Existing shared frontend styles and workflow-context module; pytest and Node.js for validation; no new runtime dependencies

**Storage**: None; the resource catalog is static application configuration and no operator state is persisted

**Testing**: Focused pytest frontend regressions, full pytest suite, Node ES-module syntax checks, and a real-browser smoke check of rendering, collapse behavior, navigation, and narrow-width layout

**Target Platform**: Existing FastAPI-served static NOC Web frontend in modern desktop and narrow-width browsers

**Project Type**: FastAPI web service with static frontend; this feature changes only frontend behavior and presentation

**Performance Goals**: Resource content is available with the existing page load; no external resource is contacted until an operator chooses its link

**Constraints**: Preserve all exact supplied URLs in one catalog; Dashboard has exactly three external Quick Links (NOC Jira, Salesforce, and Datadog) plus the internal Resources link; external destinations receive no NOC Web context; internal Resources navigation preserves valid selected-shift context; do not contact external destinations during rendering or testing; preserve Features 001–006 and their safety boundaries

**Scale/Scope**: Four collapsible resource groups, 11 external destinations, one global Resources destination, and three Dashboard external Quick Links plus one internal Resources link

## Constitution Check

*GATE: Passed before Phase 0 research and re-checked after Phase 1 design.*

| Principle | Plan response | Status |
|---|---|---|
| I. Preserve Operational Data Integrity | Keep the approved URLs unchanged, preserve selected-shift context only on internal links, and introduce no operational state or writes. | PASS |
| II. Fail Safely and Explain Failures | Treat destinations as operator-controlled links only; do not probe, preload, authenticate, or report external availability as NOC Web health. | PASS |
| III. Maintain API and UI Contract Consistency | No API contract changes are needed. Document the external-link and Dashboard UI contract and preserve existing internal navigation behavior. | PASS |
| IV. Test Operational Workflows | Add focused tests for exact inventory, page rendering, safe attributes, dashboard membership, shift isolation, and module integrity; complete a real-browser smoke check without contacting external destinations. | PASS |
| V. Prefer Simple, Observable Changes | Reuse the existing static page, shared catalog, styles, and workflow-context mechanism; use native browser disclosure behavior rather than new services, dependencies, or persisted state. | PASS |
| VI. Require Deliberate Operational Execution | Links only navigate after operator action; they do not modify tickets, trigger integrations, bypass confirmations, or expand Assistant context. | PASS |

**Post-design re-check**: PASS. The resource catalog is static, collapse state is transient, the UI
contract introduces no API or external calls, and all validation is local and non-mutating. No
constitution exception is needed.

## Project Structure

### Documentation (this feature)

```text
specs/007-add-noc-resources/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── resource-navigation.md
└── tasks.md                 # Created by /speckit-tasks
```

### Source Code (repository root)

```text
frontend/
├── index.html               # Dashboard Quick Links and global navigation
├── resources.html           # Grouped Resources directory
├── css/
│   ├── components.css       # Shared resource and link-card presentation
│   └── layout.css           # Dashboard column and responsive layout
└── js/
    ├── resources.js         # Single resource catalog and Quick Link membership
    └── workflow-context.js  # Internal selected-shift navigation preservation

tests/
└── test_frontend_modules.py # Catalog, rendering, safety, navigation, and module regressions
```

**Structure Decision**: Keep the feature in the existing static frontend. The shared catalog owns
resource names, exact URLs, groups, environment distinctions, and Dashboard Quick Link membership;
both Dashboard and Resources render from that inventory. Reuse `workflow-context.js` for internal
selected-shift links and leave external URLs unchanged. No backend or API files are in scope.

## Implementation Outline

1. Retain the four resource groups and all 11 exact URLs in the shared catalog; identify NOC Jira,
   Salesforce, and Datadog as the only Dashboard external Quick Links in that same catalog.
2. Render exactly three external shortcuts on Dashboard from the catalog and add one internal
   Resources link labeled “Resources →”. Preserve selected-shift context on the internal link only.
3. Keep the Resources page in the existing application shell and shared styles. Render all four
   groups and 11 links in the browser; make each group collapsible and expanded initially.
4. Ensure external links are visibly marked, open in a safely isolated new tab, and keep the DEMO
   distinction. Keep every link reachable without horizontal scrolling at narrow widths.
5. Add regression tests for exact catalog content, browser-rendered groups and links, group toggle
   behavior, Dashboard membership, safe link attributes, no duplicated external URLs,
   selected-shift isolation, responsive/demo presentation, and ES-module integrity. Run focused
   and full pytest suites plus a real-browser smoke check.

## Complexity Tracking

No constitutional violations or complexity exceptions are required.
