# Research: Operator Workflow

## URL-backed shift context

- **Decision**: Use `?shift=YYYY-MM-DD` on `start-shift.html`, `index.html`, `tickets.html`,
  `investigations.html`, `status.html`, and `end-shift.html`. On absence, resolve browser-local
  today and replace the location; invalid values show a safe context error and do not call a
  shift-date endpoint.
- **Rationale**: It survives refresh, deep links, and cross-page navigation without hidden session
  state, satisfying the clarified requirement.
- **Alternatives considered**: `localStorage` and in-memory globals were rejected because they
  conceal context and do not make a shared link reproducible.

## Shared UI and state reporting

- **Decision**: Create one frontend context/navigation initializer and a reusable state-panel
  renderer/style. It receives page identity, selected shift, and already-loaded source results; it
  does not fetch or mutate on its own.
- **Rationale**: Existing pages duplicate sidebar/date markup. A pure shared component prevents
  drift while preserving page-specific content and read-only behavior.
- **Alternatives considered**: A new backend workflow endpoint was rejected because it duplicates
  existing aggregates and could cause unnecessary cache reads/refreshes.

## Existing data boundaries

- **Decision**: Continue using `backend.services.jira_cache.get_jira_cache_health()` for Jira
  freshness and `backend.services.tickets.get_operational_work_summary()` for local NOC context.
  Views render these sources independently.
- **Rationale**: Cache health is already non-writing (`tests/test_jira_cache.py` and
  `tests/test_status.py` assert it); the local summary already excludes Jira-managed fields.
- **Alternatives considered**: Copying Jira fields into local summaries or refreshing cache on
  navigation was rejected as data duplication and hidden automation.

## Confirmation gates

- **Decision**: A dialog immediately precedes every in-scope mutation. Existing tracking and Jira
  actions keep their `confirmed: true` payload only after confirmation. Start Shift gains an
  additive required `confirmed` request body and rejects omitted/false confirmation before service
  execution.
- **Rationale**: Existing Start Shift POST has no request confirmation, while ticket mutations
  already validate it. This closes the only identified contract gap without a breaking path change.
- **Alternatives considered**: Browser `confirm()` alone and automatic `confirmed: true` in
  `frontend/js/api.js` were rejected because callers can mutate without an explicit, testable gate.

## Failure handling

- **Decision**: Keep valid independent sections visible. State labels distinguish cache stale from
  cache unavailable, local data unavailable, investigation unavailable, and request/action errors;
  errors offer retry only where retry is safe and explicit.
- **Rationale**: Existing API errors expose actionable HTTP details, cache health exposes
  `freshness`, and the specification prohibits an unavailable source from masking other data.
- **Alternatives considered**: A whole-page failure overlay and automatic retry/refresh were
  rejected because both obscure healthy context or create hidden work.
