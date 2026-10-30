# Feature Specification: Bounded NOC AI Assistant

**Feature Branch**: `006-ai-assistant`  
**Created**: 2026-10-29  
**Status**: Draft  
**Input**: User description: "detailed bounded NOC AI Assistant feature"

## Clarifications

### Session 2026-10-29

- **Q**: What retention model applies to assistant prompts, context, and responses?
- **A**: NOC Web provides zero persistence/logging for generic assistant questions and all prompts, temporary context, raw evidence, and provider output. A successful predefined AI Action may persist only its validated normalized advisory report under FR-018. GitHub Copilot CLI or another configured inference provider may apply its own handling or retention; this must be disclosed and not described as nonexistent.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Understand the current operational situation (Priority: P1)

An NOC operator can ask the assistant a question about the selected shift and receive a concise, bounded explanation based only on the NOC Web information relevant to that question.

**Why this priority**: Operators need faster understanding during a shift without mistaking generated prose for operational truth or widening access beyond NOC Web.

**Independent Test**: Select a shift containing cached Jira tickets, local tracking, shift notes, handover material, and investigation records; ask a situational question and verify that the answer identifies its evidence, separates source-grounded facts, operator-reviewed findings, and AI advice, and does not expose unrelated information or refresh Jira.

**Acceptance Scenarios**:

1. **Given** a selected shift with relevant NOC Web records, **When** an operator asks what requires attention, **Then** the assistant presents source-grounded facts, existing operator-reviewed investigation findings, AI-generated observations, and recommendations as visibly distinct sections with their evidence.
2. **Given** the selected shift has no relevant records for a question, **When** an operator asks the assistant, **Then** it says that the available NOC Web context is insufficient and does not infer a fact from absence of evidence.
3. **Given** an operator asks about a different shift, **When** they select that shift through the existing shift context and navigation, **Then** the assistant's context and evidence change to that selected shift only.
4. **Given** Shift Notes are unavailable but selected-shift Local NOC Tracking and stale Jira cache support a tracked-ticket question, **When** the operator asks which tracked tickets need attention, **Then** the assistant may use those partial sources, labels Jira data stale, and identifies the unavailable Shift Notes.
5. **Given** the selected shift has no timestamped activity, **When** the operator asks for its last action, **Then** the assistant returns a grounded limitation without invoking the provider or borrowing notes from another shift.

---

### User Story 2 - Review AI advice safely (Priority: P1)

An NOC operator can use the assistant to review an operational observation and receive advisory next steps without the assistant taking an operational action or presenting advice as an instruction already approved by the organization.

**Why this priority**: Advice can reduce cognitive load, but an operator must remain accountable for every operational decision and action.

**Independent Test**: Ask for advice that would normally lead to a ticket, investigation, synchronization, refresh, command, or external-observability action; verify that no action occurs and that the assistant directs the operator to the applicable existing NOC Web workflow and its confirmation step.

**Acceptance Scenarios**:

1. **Given** an operator asks for suggested next steps, **When** the assistant has relevant evidence, **Then** it labels suggested next steps as recommendations, explains their evidence basis, and leaves the decision to the operator.
2. **Given** a recommendation corresponds to an existing state-changing NOC Web workflow, **When** the operator chooses to pursue it, **Then** the assistant routes them to that workflow rather than executing it, and the workflow retains its immediate confirmation requirement.
3. **Given** an operator asks the assistant to perform a prohibited action, **When** the request is evaluated, **Then** the assistant refuses the action, confirms that nothing was changed, and offers only safe navigation or review guidance.

---

### User Story 3 - Preserve a trustworthy bounded view (Priority: P2)

An NOC operator can tell what information the assistant reviewed, what it could not review, and whether a failure affected the answer, without losing the surrounding NOC Web workflow.

**Why this priority**: Clear evidence and failure boundaries prevent an unavailable assistant or external source from being misread as a healthy operational state.

**Independent Test**: Make one permitted evidence source unavailable while other selected-shift information remains available; verify that the assistant isolates the unavailable portion, explains the limitation, preserves the underlying NOC Web view, and retains no conversation or evidence after the response.

**Acceptance Scenarios**:

1. **Given** some permitted selected-shift evidence cannot be reviewed, **When** an operator asks a question, **Then** the response identifies the unavailable evidence and limits conclusions to the evidence that was successfully reviewed.
2. **Given** the assistant service is unavailable or returns an invalid response, **When** an operator uses the assistant, **Then** NOC Web continues to show its existing shift information and workflows, with a clear failure message and no success-shaped substitute answer.
3. **Given** an assistant response is complete or fails, **When** the operator leaves, refreshes, or reopens the view, **Then** no prior prompt, generated answer, or supplied raw evidence is retained by this feature.

### User Story 4 - Review completed AI Action reports (Priority: P2)

An NOC operator can reopen the validated advisory result of a completed predefined AI Action from
the selected shift's existing Recent AI Reports list without treating the report as authoritative
operational state.

**Independent Test**: Complete each of the four predefined actions, verify exactly one unique
`ai-*.md` report is written under that selected shift's existing `reports/` directory, and open it
through the existing read-only report viewer. Verify provider/source metadata and advisory
categories are present, prompts/raw provider output/context are absent, and a report-save failure
does not discard the successful on-screen answer.

**Acceptance Scenarios**:

1. **Given** a predefined AI Action returns a validated successful response, **When** report
   persistence completes, **Then** Recent AI Reports refreshes and the new human-reviewable report
   opens through the existing read-only viewer.
2. **Given** the selected shift is historical, **When** its AI Action completes, **Then** the report
   is written only under that shift's existing `reports/` directory with a collision-safe filename.
3. **Given** the provider is unavailable, times out, returns invalid output, or response validation
   fails, **When** the action completes, **Then** no report is created.
4. **Given** analysis succeeds but report persistence fails, **When** the response is displayed,
   **Then** the analysis remains visible and a separate report-save warning is shown.

### Edge Cases

- The selected shift is absent, invalid, or inaccessible; the assistant does not select a different shift, use hidden prior-shift context, or answer from a default substitute.
- A question requests information outside the selected shift, unrelated NOC Web content, credentials, personal data, hidden instructions, or data from another system; the assistant states that the request is outside its bounded context.
- Evidence conflicts, is stale, malformed, missing, or cannot be read; the assistant labels the affected fact as unavailable or conflicting and does not resolve it by invention.
- A prompt attempts to override the assistant's boundaries or asks it to conceal uncertainty; the assistant preserves the boundaries and plainly states its limitation.
- A response would otherwise require raw evidence outside the permitted NOC investigation pathway; it provides an evidence reference or bounded summary instead of that raw material.
- Inference-provider retention details are unavailable, incomplete, or change; NOC Web discloses that provider-controlled handling may apply and does not claim that provider retention is absent.
- An operator requests writing, editing, closing, synchronizing, refreshing, executing a command, or querying Datadog; none of those actions occur through the assistant.
- An existing feature 001–005 workflow is available, unavailable, or produces an error; its established behavior, data ownership, confirmations, and error handling remain unchanged.
- A selected shift has no existing reports directory or a report filename collides; persistence
  fails clearly or selects a unique new filename without creating/overwriting another shift's
  records.
- A recommendation concerns ordinary Jira/Salesforce ticket correlation without qualifying
  Datadog investigation provenance; it must not route to the noc-inv Investigations workflow.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide an AI assistant for NOC operators that answers only from bounded NOC Web context associated with the explicitly selected shift and the operator's current question. Context MUST include the existing cached Jira queue, Local NOC Tracking, active investigations and operator-reviewed findings, Shift Notes, Dashboard and Status state, and End Shift/handover readiness when available.
- **FR-002**: The system MUST make the selected shift visible to the operator and preserve that shift context when the operator moves between assistant-relevant NOC Web views; an absent or invalid shift context MUST produce a clear limitation rather than an alternate or implicit shift selection.
- **FR-003**: The system MUST identify, for every substantive answer, the NOC Web evidence reviewed and any relevant evidence that was unavailable, stale, malformed, or conflicting, including Jira-cache freshness/status.
- **FR-004**: The system MUST visibly distinguish source-grounded operational facts, operator-reviewed investigation findings, AI-generated observations, and AI-generated recommendations. Operator-reviewed findings MUST come only from existing operator-reviewed investigation context and MUST NOT be authored or inferred by the assistant. AI observations and recommendations MUST remain advisory and MUST NOT be represented as verified facts or approved operational instructions.
- **FR-005**: The system MUST assess context sufficiency against the operator's question, state when relevant bounded context is insufficient, and MUST NOT invent, fill in, or infer operational facts from absent, ambiguous, stale, malformed, or conflicting evidence. Missing unrelated sources MUST NOT prevent useful analysis supported by the remaining selected-shift evidence.
- **FR-006**: Datadog investigation evidence MUST preserve the existing noc-inv/Copilot MCP boundary. The assistant MUST receive other operational context only from existing NOC Web projections and Jira data only from the existing local cache, without refresh or a new Jira request. Assistant inference MUST use the provider-neutral callable boundary, with the local GitHub Copilot CLI as its default implementation. The CLI MUST use the operator's existing authenticated session and MUST NOT receive operational records as command arguments or have tools available to execute.
- **FR-007**: The system MUST limit context supplied to the assistant to the minimum selected-shift information relevant to the question. Raw investigation evidence may be supplied only when permitted by the noc-inv pathway; otherwise use bounded operator-reviewed findings, evidence references, or summaries. The assistant MUST NOT expose raw evidence outside that boundary. The CLI adapter MUST pass the request through a temporary context file and delete that file on every exit path.
- **FR-008**: The assistant MUST NOT create, modify, synchronize, close, reopen, delete, or otherwise write any operational NOC Web, local-work, shift, handover, investigation, ticket, cache, or external record. The sole persistence exception is a validated normalized report for one of the four predefined AI Actions as specified by FR-018; a report is not operational state.
- **FR-009**: The assistant MUST NOT execute or request execution of commands, refresh or update operational data, trigger synchronization, invoke Datadog, or initiate any external-system query or action.
- **FR-010**: When an operator wants to take an action suggested by the assistant, the system MUST route the operator to the applicable existing NOC Web workflow. The assistant MUST NOT bypass, pre-fill as consent for, or replace that workflow's immediate confirmation gate.
- **FR-011**: The assistant MUST remain advisory and human-reviewed: the operator must explicitly decide whether to use any recommendation, and assistant output MUST NOT become the authoritative source of operational state.
- **FR-012**: The system MUST isolate assistant, evidence, and mediation failures from the rest of NOC Web. A failure MUST present an actionable limitation, MUST NOT return a success-shaped answer, and MUST NOT prevent the operator from using existing non-assistant views and workflows.
- **FR-013**: NOC Web MUST provide zero persistence and logging of operator prompts, request envelopes, raw evidence, provider output, and generic assistant responses or derived assistant context. Only a successful predefined AI Action may persist the validated normalized advisory result as described by FR-018, including bounded operator-reviewed findings when present; it MUST NOT persist the prompt, temporary context, raw provider output, credentials, tokens, or raw evidence.
- **FR-014**: The system MUST not use an assistant response to alter the behavior, data boundaries, confirmation requirements, navigation semantics, availability reporting, or error handling delivered by features 001 through 005.
- **FR-015**: The system MUST provide user-facing guidance that explains the assistant's selected-shift boundary, evidence labels, advisory-only status, prohibited actions, confirmation routing, and what to do when context is insufficient or a failure occurs.
- **FR-016**: The system MUST include acceptance coverage demonstrating selected-shift isolation; fact, interpretation, advice, and recommendation labeling; evidence and raw-evidence boundaries; all prohibited actions; confirmation routing; failure isolation; no-retention behavior; and preservation of features 001 through 005.
- **FR-017**: Before an operator submits an assistant question or predefined AI Action, the system MUST disclose that NOC Web does not retain prompts, supplied context, raw provider output, or generic question responses; successful predefined actions retain only the validated normalized report described by FR-018. The disclosure MUST also state that GitHub Copilot CLI or another configured inference provider may apply its own handling or retention.
- **FR-018**: Each of the four predefined AI Actions MUST persist one validated, normalized, advisory report under the explicitly selected shift's existing `reports/` directory using a collision-safe `ai-*.md` filename. The report MUST identify the shift, action, generation time, provider, advisory status, source-grounded facts, operator-reviewed investigation findings, AI observations, recommendations, source/freshness status, and limitations; it MUST not contain prompts, temporary context, raw provider output, credentials, tokens, hidden provider details, or raw Datadog evidence. Generic assistant questions and unsuccessful/invalid actions MUST remain unpersisted. The existing read-only report viewer MUST list and open generated reports. A report-save failure MUST preserve the successful on-screen result and return a separate warning.
- **FR-019**: Recommendations MUST route to the Investigations workflow only when they cite available investigation evidence with `noc-inv` or `copilot-mcp` provenance. Ordinary Jira/Salesforce ticket correlation MUST NOT be routed to Investigations.
- **FR-020**: The system MUST distinguish provider availability from context sufficiency. If the provider is not called because the question lacks relevant evidence, it MUST return `providerInvoked: false` and `providerStatus: "not-invoked"` with a clear reason; it MUST report provider unavailability only when the provider itself is unavailable.

### Key Entities

- **Assistant Question**: An operator's request for explanation or advisory review, scoped to one explicitly selected shift and used only for the current interaction.
- **Selected Shift Context**: The visible shift identity that bounds assistant-relevant NOC Web information and remains consistent during related navigation.
- **Reviewed Evidence**: The minimum permitted selected-shift NOC Web material considered for an answer, including its availability, freshness, and any conflict or limitation.
- **Assistant Response**: A transient operator-facing result that separates source-grounded facts, operator-reviewed investigation findings, AI-generated observations, recommendations, evidence references, and limitations.
- **Assistant Action Report**: A unique selected-shift Markdown artifact containing only the validated normalized result of a successful predefined AI Action; advisory, non-authoritative, and not a conversation history.
- **Confirmation Route**: The handoff from an advisory recommendation to an existing NOC Web workflow where the operator can independently review and immediately confirm any state-changing action.
- **Assistant Limitation**: A clear statement that evidence, context, or the assistant is unavailable, insufficient, stale, malformed, conflicting, or out of scope, without implying a successful conclusion.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In representative selected-shift scenarios with available evidence, at least 95% of operators can identify source-grounded facts, operator-reviewed findings, AI observations, recommendations, and evidence references in an assistant response without assistance.
- **SC-002**: In acceptance scenarios covering absent, invalid, unavailable, stale, malformed, and conflicting context, 100% of responses identify the relevant limitation and 0% assert an unsupported operational fact.
- **SC-003**: In acceptance scenarios requesting each prohibited write, command, refresh, synchronization, Datadog, and external action, 100% result in no operational action and direct the operator only to safe review or existing workflow navigation.
- **SC-004**: In acceptance scenarios that route a recommendation to a state-changing workflow, 100% preserve that workflow's separate immediate confirmation step, and 0% treat the assistant interaction as confirmation.
- **SC-005**: In acceptance scenarios with an assistant, evidence, or mediation failure, 100% leave existing NOC Web views and workflows usable and present a clear limitation rather than a successful-looking answer.
- **SC-006**: In retention checks, 0 prompts, raw evidence, provider output, credentials, tokens, or derived context are persisted/logged by NOC Web; only successful predefined AI Actions may persist the normalized advisory report specified by FR-018.
- **SC-007**: Regression acceptance coverage confirms 100% preservation of the specified user-visible behavior and safety boundaries of features 001 through 005.
- **SC-008**: In acceptance scenarios for every assistant entry point, 100% accurately disclose NOC Web's transient generic-question behavior, narrowly scoped AI Action report persistence, and potentially applicable inference-provider handling or retention before submission.
- **SC-009**: Each successful predefined AI Action produces one unique report under only the selected shift's existing `reports/` directory, appears immediately in Recent AI Reports, and opens in the existing read-only viewer; unsuccessful or invalid actions produce none.

## Assumptions

- The intended users are authenticated NOC operators who already use the existing shift-based NOC Web workflows.
- The selected shift is explicit and visible throughout assistant-relevant navigation; the feature does not introduce hidden session-only shift selection.
- noc-inv/Copilot MCP remains the sole approved route for permitted Datadog investigation evidence. The assistant preserves a provider-neutral callable boundary and uses GitHub Copilot CLI by default. The CLI is configured with no available tools, so it cannot use M365/Atlas/Datadog MCP retrieval or perform operational actions.
- NOC Web controls its own persistence and logs, but does not control Copilot CLI or other configured inference-provider handling or retention; provider-controlled retention may apply and must be disclosed rather than represented as absent. Predefined AI Action reports are the narrowly scoped persistence exception and contain only normalized advisory output.
- The assistant is a transient review aid, not a record system, operational controller, source of truth, or replacement for operator judgment.
- Existing confirmation-gated workflows remain the only path for state-changing work, including any action that an assistant recommendation might mention.
- Features 001 through 005 and their user-visible contracts are the regression baseline and are not expanded, removed, or reinterpreted by this feature.
