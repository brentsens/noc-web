# Quickstart: Jira Cache Health Visibility

## Prerequisites

- Run commands from the repository root.
- Use a local test environment; tests must not use a real NOC directory, Jira service, or
  credentials.

## Focused validation

1. Run the cache and Status tests:

   ```bash
   pytest tests/test_jira_cache.py tests/test_status.py
   ```

2. Verify the cases described in [data-model.md](data-model.md):
   - a valid cache refreshed less than 30 minutes ago is current;
   - a valid cache refreshed exactly 30 minutes ago or longer is stale;
   - missing, malformed, and invalid-timestamp caches are unavailable;
   - computing health leaves cache and ticket data unchanged and does not trigger a refresh.

3. Run the full existing test suite:

   ```bash
   pytest
   ```

## Operator validation

1. Start the local application using the repository's normal development command.
2. Open the Status page for a valid shift date.
3. Confirm the Jira cache metric reports availability, last successful refresh, and current or
   stale freshness consistent with [contracts/status-api.md](contracts/status-api.md): current is
   less than 30 minutes old, and stale is 30 minutes old or older.
4. Make the cache unavailable in a local test environment and reload the page. Confirm the metric
   reports unavailable while existing Status page information remains visible.
5. Confirm that viewing or reloading the Status page does not trigger a Jira refresh or alter cache
   or ticket data.
