# Feature Specification: NOC Resources Experience

**Feature Branch**: `007-add-noc-resources`  
**Created**: 2026-10-30  
**Status**: Draft  
**Input**: User description: "Create a professional NOC Resources experience with one global navigation destination, four responsive groups containing 11 exact external shortcuts, and Dashboard Quick Links for NOC Jira, Salesforce, and Datadog."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Find an operational resource (Priority: P1)

An operator can open one Resources destination from the application navigation and find external systems grouped by the kind of work they support, without scanning a long list of links in the sidebar or Dashboard.

**Why this priority**: Operators need fast, predictable access to the systems used during daily NOC work while keeping primary application navigation focused.

**Independent Test**: Open Resources in a supported browser and verify that all four groups and all 11 supplied destinations are visibly rendered under their expected group, with DEMO SES clearly distinguished from production SES environments.

**Acceptance Scenarios**:

1. **Given** an operator is using any NOC Web page, **When** they choose the single Resources destination from global navigation, **Then** they reach a Resources page visibly containing all 11 destinations in the SES Environments, Tickets & Support, Documentation, and Observability groups.
2. **Given** the Resources page is open, **When** the operator scans the SES Environments group, **Then** USPRI SES, EU SES, and MEXPRI SES are identifiable as production environments and DEMO SES is visibly distinguished.
3. **Given** an operator views Resources at desktop or narrow browser width, **When** the page is displayed, **Then** each group and its destinations remain legible and usable without horizontal page scrolling; groups are expanded by default on desktop, and operators may collapse groups while retaining access to their contents.

---

### User Story 2 - Open a frequent destination from Dashboard (Priority: P1)

An operator can open the most frequently used external destinations directly from Dashboard, while still having a clear route to the complete Resources directory.

**Why this priority**: The three high-frequency systems should be immediately reachable without making Dashboard or global navigation a general bookmark list.

**Independent Test**: Open Dashboard and verify that its only external Quick Links are NOC Jira, Salesforce, and Datadog, with a separate link to the full Resources page.

**Acceptance Scenarios**:

1. **Given** the operator is on Dashboard, **When** they view Quick Links, **Then** NOC Jira, Salesforce, Datadog, and the internal Resources link are shown, and no other external resource is presented as a Dashboard Quick Link.
2. **Given** the operator wants a destination not among the three Quick Links, **When** they select the full Resources link, **Then** they can find it in the appropriate Resources group.

---

### User Story 3 - Navigate externally without sharing NOC Web context (Priority: P1)

An operator can deliberately open a configured external destination in a separate browser tab without sending selected-shift, ticket, investigation, Assistant, or other NOC Web context to that destination.

**Why this priority**: Resource shortcuts must remain operator-controlled navigation and must not expose operational context or create an unintended integration.

**Independent Test**: Open each configured destination and verify it uses its exact approved URL in a new tab, does not alter the originating NOC Web page, and receives no NOC Web context in its destination URL.

**Acceptance Scenarios**:

1. **Given** an external resource link is shown, **When** the operator opens it, **Then** it opens in a new browser tab with safe separation from the originating NOC Web page.
2. **Given** an operator has selected a shift or is viewing ticket, investigation, or Assistant information, **When** they open an external resource, **Then** the configured destination remains unchanged and receives none of that NOC Web context.
3. **Given** an operator follows internal NOC Web navigation to Resources, **When** a valid selected-shift context is present, **Then** the internal navigation preserves it; external destinations do not receive it.

### Edge Cases

- A resource destination is unavailable or requires authentication: NOC Web continues to act only as a navigation shortcut and does not probe, authenticate to, or preload the destination.
- A resource link is opened from a selected-shift workflow: the originating workflow remains intact, and no shift identifier is appended to the external URL.
- A narrow browser layout cannot display all group contents at once: every resource remains reachable and group labels remain understandable.
- A Resources page opens in a supported browser: all four groups and all 11 destinations render without requiring any external destination to load.
- A future resource destination is not one of the three high-frequency destinations: it appears in its Resources group and is not added to Dashboard Quick Links unless the defined Quick Link set is deliberately changed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: NOC Web MUST provide exactly one Resources destination in global application navigation; individual external systems MUST NOT be added as separate sidebar destinations.
- **FR-002**: The Resources experience MUST organize destinations into SES Environments, Tickets & Support, Documentation, and Observability groups.
- **FR-003**: The SES Environments group MUST contain the following exact destinations:
  - USPRI SES — `https://app.uspri.sesami.io/aaa/login?targetUrl=https://app.uspri.sesami.io/`
  - EU SES — `https://app.sesami.io/aaa/login?targetUrl=https://app.sesami.io/`
  - MEXPRI SES — `https://app.mexpri.sesami.io/`
  - DEMO SES — `https://app.demo.sesami.io/aaa/login?targetUrl=https://app.demo.sesami.io/`
- **FR-004**: The Tickets & Support group MUST contain the following exact destinations:
  - NOC Jira — `https://sesamidevel.atlassian.net/issues/?filter=22992`
  - Salesforce — `https://sesami.lightning.force.com/lightning/o/Case/list?filterName=NOC_SES_Case`
  - DevOps Ticket Portal — `https://sesamidevel.atlassian.net/servicedesk/customer/portal/199`
- **FR-005**: The Documentation group MUST contain the following exact destinations:
  - NOC Confluence — `https://sesamidevel.atlassian.net/wiki/spaces/NOC/overview`
  - SES Confluence — `https://sesami-io.atlassian.net/wiki/home?cloudId=8986e79a-6c2a-4e0d-bb65-4a57e0f68db9&source=peopleMenu`
  - Atlassian Home — `https://home.atlassian.com/o/87e5c9f6-4c36-46da-a68f-a39ba95b7c5a/?cloudId=8986e79a-6c2a-4e0d-bb65-4a57e0f68db9`
- **FR-006**: The Observability group MUST contain the following exact destination:
  - Datadog — `https://app.datadoghq.com/apm/home?env=%2A&graphType=service_map&shouldShowLegend=true&traceQuery=&view=services`
- **FR-007**: Every external resource MUST visibly identify its external navigation and MUST open in a new browser tab with safe separation from the originating page.
- **FR-008**: DEMO SES MUST be visually distinguishable from production SES environments.
- **FR-009**: Resource groups MUST be compact, collapsible, and usable at desktop and narrow browser widths without horizontal page scrolling. Groups MUST be expanded by default on desktop; operators MAY collapse groups while preserving access to every resource.
- **FR-010**: Dashboard MUST provide exactly four Quick Links: external NOC Jira, Salesforce, and Datadog shortcuts, and an internal link labeled “Resources →” to the full Resources page.
- **FR-011**: Resource destinations MUST be maintained as one shared resource inventory; individual pages MUST NOT duplicate the external URL inventory.
- **FR-012**: Opening an external resource MUST NOT add or transmit selected-shift, ticket, investigation, Assistant, or other NOC Web context.
- **FR-013**: Resources MUST remain operator-controlled navigation shortcuts. NOC Web MUST NOT probe, fetch, preload, authenticate to, or integrate directly with these external destinations.
- **FR-014**: Resources MUST NOT be added to AI Assistant context solely because they are listed on the Resources page.
- **FR-015**: Internal NOC Web navigation to Resources MUST preserve valid selected-shift context; external navigation MUST NOT require or receive that context.
- **FR-016**: The Resources experience MUST use the established NOC Web application presentation and remain usable alongside existing Dashboard and operational workflows.
- **FR-017**: The feature MUST preserve existing behavior and safety boundaries for Features 001–006, including read-only behavior, operational confirmation requirements, and existing selected-shift workflows.
- **FR-018**: Opening Resources in a supported browser MUST visibly render all four resource groups and all 11 configured destinations; inventory configuration alone does not satisfy this requirement.

### Key Entities *(include if feature involves data)*

- **Resource Group**: A named category of external destinations, with an ordered set of resources and presentation characteristics.
- **Resource Shortcut**: An operator-controlled link identified by name and exact destination URL, grouped by purpose and visibly marked as external.
- **Dashboard Quick Link**: One of the three designated high-frequency external shortcuts presented on Dashboard.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On opening Resources in a supported browser, operators can see all four specified groups and all 11 destinations, each under the correct group and matching its supplied URL exactly.
- **SC-002**: From Dashboard, an operator can open NOC Jira, Salesforce, or Datadog in one selection, and can reach any other configured resource through the full Resources page in no more than two selections.
- **SC-003**: Dashboard presents exactly four Quick Links: the three specified external destinations and an internal link labeled “Resources →”.
- **SC-004**: Operators can distinguish DEMO SES from all three production SES environments at a glance and reach every resource at desktop and narrow widths without horizontal page scrolling; all groups are expanded by default on desktop and can be collapsed by the operator.
- **SC-005**: All external destinations open in a separate tab without selected-shift or other NOC Web context, and no resource destination is automatically contacted by NOC Web.
- **SC-006**: The feature adds no external service integration and does not change existing Features 001–006 workflows or confirmation boundaries.

## Assumptions

- The supplied resource names and URLs are the approved inventory for this feature; authentication, availability, and authorization remain the responsibility of each destination.
- USPRI SES, EU SES, and MEXPRI SES are production environments; DEMO SES is non-production.
- The Dashboard Quick Link set is intentionally limited to NOC Jira, Salesforce, and Datadog.
- Operators may use the existing application navigation and selected-shift workflow; resource shortcuts do not create or modify operational records.
- Resource groups are expanded by default on desktop; operators may collapse them on any layout, and all destinations remain discoverable and accessible.
