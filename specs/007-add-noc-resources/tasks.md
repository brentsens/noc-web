---
description: "Task list for the NOC Resources experience"
---

# Tasks: NOC Resources Experience

**Input**: Design documents from `specs/007-add-noc-resources/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/resource-navigation.md`, and `quickstart.md`

**Tests**: Tests are required by the feature's acceptance requirements. Add focused regression
coverage before implementation and verify the actual page in a browser; synthetic DOM tests alone
do not satisfy browser-rendering requirements.

**Organization**: Tasks are grouped by the three independently testable user stories. Existing
frontend infrastructure is reused; no new dependencies, backend routes, external integrations, or
persisted state are introduced.

## Phase 1: Setup

**Purpose**: Project initialization

No setup tasks are required. The repository, static frontend, test environment, and shared styles
already exist.

---

## Phase 2: Foundational

**Purpose**: Blocking prerequisites shared by all user stories

No additional foundation is required. The shared resource catalog and selected-shift navigation
helper already exist.

---

## Phase 3: User Story 1 - Find an operational resource (Priority: P1) - MVP

**Goal**: Operators can find all 11 exact external destinations in four responsive, collapsible
groups, with DEMO SES distinguished from production environments.

**Independent Test**: Open Resources in a supported browser and verify that all groups and links
render, every group starts expanded, each group can be collapsed and reopened, DEMO SES is distinct,
and every destination remains reachable at narrow widths without horizontal scrolling.

### Tests for User Story 1

- [X] T001 [US1] Add regression coverage in `tests/test_frontend_modules.py` for the four resource groups, all 11 exact catalog URLs, one Resources sidebar item per page, safe external-link attributes, DEMO differentiation, and initially expanded group markup.

### Implementation for User Story 1

- [X] T002 [US1] Update `frontend/resources.html` to render each catalog group as an operator-collapsible disclosure, initially expanded, while rendering all 11 catalog destinations.
- [X] T003 [P] [US1] Update `frontend/css/components.css` to style group disclosure controls and resource cards responsively without horizontal page overflow.
- [X] T004 [US1] Ensure exactly one Resources sidebar destination is present in `frontend/index.html`, `frontend/shift-notes.html`, `frontend/tickets.html`, `frontend/investigations.html`, `frontend/ai-actions.html`, `frontend/assistant.html`, `frontend/resources.html`, `frontend/start-shift.html`, `frontend/status.html`, `frontend/health.html`, and `frontend/end-shift.html`.

**Checkpoint**: The Resources directory is visibly rendered in a browser, collapsible, responsive,
and independently usable.

---

## Phase 4: User Story 2 - Open a frequent destination from Dashboard (Priority: P1)

**Goal**: Dashboard offers exactly three external Quick Links—NOC Jira, Salesforce, and Datadog—
plus the internal “Resources →” link.

**Independent Test**: Open Dashboard and verify that exactly those four links render, the external
URLs match the shared catalog, and the internal link opens the Resources directory.

### Tests for User Story 2

- [X] T005 [US2] Add a Dashboard regression test in `tests/test_frontend_modules.py` that verifies the exact four Quick Links, shared catalog URLs, safe external-link attributes, and the internal Resources route.

### Implementation for User Story 2

- [X] T006 [US2] Mark only NOC Jira, Salesforce, and Datadog as Dashboard Quick Links in `frontend/js/resources.js`, preserving all 11 exact resource URLs.
- [X] T007 [US2] Render the three catalog-selected external shortcuts and the internal “Resources →” link in `frontend/index.html` without duplicating external URLs.
- [X] T008 [P] [US2] Update `frontend/css/components.css` and `frontend/css/layout.css` so Dashboard Quick Links remain compact and usable at desktop and narrow widths.

**Checkpoint**: Dashboard provides only the three approved external shortcuts and the full-directory
route.

---

## Phase 5: User Story 3 - Navigate externally without sharing NOC Web context (Priority: P1)

**Goal**: External resources remain operator-controlled shortcuts that never receive shift, ticket,
investigation, Assistant, or other NOC Web context.

**Independent Test**: With a valid selected shift, verify internal navigation preserves the shift
while each external destination remains exactly equal to its catalog URL and has safe new-tab
attributes.

### Tests for User Story 3

- [X] T009 [US3] Add context-isolation regressions in `tests/test_frontend_modules.py` verifying selected-shift preservation for internal Resources navigation, unchanged external URLs and safe new-tab attributes, and no resource catalog injection into Assistant context.

### Implementation for User Story 3

- [X] T010 [US3] Ensure `frontend/js/workflow-context.js` adds selected-shift context only to internal NOC Web links, including Resources, and never rewrites external resource URLs.

**Checkpoint**: Internal workflow context remains intact, and external shortcuts receive no NOC Web
context.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate all stories, browser behavior, and existing workflows

- [X] T011 Run focused and full pytest suites, frontend ES-module validation, and `git diff --check` using the commands in `specs/007-add-noc-resources/quickstart.md`.
- [X] T012 Perform the real-browser smoke check in `specs/007-add-noc-resources/quickstart.md` against `frontend/index.html` and `frontend/resources.html` at desktop and 320 CSS-pixel widths; verify rendering, group toggles, selected-shift isolation, and link attributes without activating external links.

> T012 completed by operator in an actual browser: all groups and links rendered, disclosures
> toggled, DEMO styling and Dashboard links were correct, narrow layout was usable, no console
> errors occurred, and Resources loading made no automatic external requests.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No tasks; existing project setup is reused.
- **Foundational (Phase 2)**: No tasks; existing catalog and workflow-context infrastructure are reused.
- **User Stories (Phase 3+)**: US1 and US2 are independently valuable. US3 validates safe navigation across both and follows them.
- **Polish (Phase 6)**: Depends on all user stories being complete.

### User Story Dependencies

- **User Story 1 (P1)**: Can start immediately; no dependency on another story.
- **User Story 2 (P1)**: Can start immediately; consumes the existing shared resource catalog.
- **User Story 3 (P1)**: Follows US1 and US2 so context-isolation coverage includes both Resources and Dashboard links.

### Within Each User Story

- Add or update focused regressions before the corresponding behavior changes.
- For US1, T002 and T003 can run in parallel after T001 because they change separate files; T004 follows T002 because both update Resources navigation markup.
- For US2, T006 precedes T007 because Dashboard consumes catalog metadata. T007 and T008 can run in parallel after T006 because they update separate files.
- For US3, T009 precedes T010.
- T011 and T012 run after all implementation tasks; the browser smoke check is mandatory and is not replaced by synthetic DOM coverage.

### Parallel Opportunities

- **US1**: T002 and T003 can run in parallel after T001.
- **US2**: T007 and T008 can run in parallel after T006.
- The story phases share `tests/test_frontend_modules.py` and `frontend/css/components.css`; coordinate or serialize edits to those files.

## Parallel Example: User Story 1

After T001 establishes the expected behavior, run the markup and style work together:

```text
Task: T002 Implement collapsible resource groups in frontend/resources.html
Task: T003 Style group disclosures and responsive cards in frontend/css/components.css
```

## Implementation Strategy

### MVP First (User Story 1)

1. Complete T001 through T004.
2. Verify the Resources page in a real browser at desktop and narrow widths.
3. Stop and validate that all 11 resources are available without external requests.

### Incremental Delivery

1. Deliver the Resources directory and its global navigation entry (US1).
2. Add the three Dashboard shortcuts and Resources route (US2).
3. Verify external-link and selected-shift isolation (US3).
4. Run all automated and required browser validation (Phase 6).

## Notes

- Every task uses the required checkbox, sequential ID, optional parallel marker, story label for user-story work, and an explicit repository path.
- No dependencies or tooling are added by this plan.
- External resources must not be opened or probed during validation.
