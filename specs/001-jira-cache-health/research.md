# Research: Jira Cache Health Visibility

## Decision: Reuse the local cache reader and add a dedicated health projection

**Rationale**: `read_jira_cache` already reads only the local JSON cache and returns no cache for
missing, unreadable, malformed, or structurally invalid data. A health projection can validate the
recorded `refreshedAt` value and classify freshness without calling the Jira discovery or refresh
paths. This preserves the feature's read-only requirement.

**Alternatives considered**:

- Call the existing ticket-queue refresh operation: rejected because it contacts Jira and writes
  the cache.
- Infer health only from ticket count: rejected because an empty cache can be valid and provides no
  freshness information.
- Add a separate health endpoint: rejected because the existing Status response and page already
  aggregate operational status, so an additive field is simpler and keeps one load path.

## Decision: Apply the approved 30-minute freshness policy

**Rationale**: The inspected cache service records an ISO 8601 UTC `refreshedAt` value, and the
ticket queue passes it through. The status service, configuration, and tests contain no existing
freshness, staleness, age, interval, timeout, or TTL policy. The approved operational policy is:
current when the last successful refresh occurred less than 30 minutes ago, stale when it occurred
30 minutes ago or longer, and unavailable when the cache or valid timestamp cannot be read.

**Alternatives considered**:

- Treat every readable cache as current: rejected because it does not meet the stale-data
  requirement.
- Trigger refresh when stale: rejected because the feature is informational and read-only.
- Select a different duration without an approved policy: rejected because it would be arbitrary.

## Decision: Use explicit three-state health

**Rationale**: A `current`, `stale`, or `unavailable` freshness state plus availability and refresh
time lets the UI communicate every required condition without interpreting raw cache data. Invalid
or absent timestamps are `unavailable`, never `current`. Valid timestamps use the approved
30-minute policy; a stale result does not trigger a refresh.

**Alternatives considered**:

- Boolean `stale`: rejected because it cannot distinguish unavailable cache information from a
  readable current cache.
- Pass the raw cache file to the UI: rejected because validation and policy belong in the backend
  service boundary.
