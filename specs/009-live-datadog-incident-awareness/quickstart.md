# Quickstart: Live Datadog Incident Awareness

## Prerequisites

- The existing noc-web workstation configuration and writable NOC root.
- The authenticated GitHub Copilot CLI and configured Datadog MCP server.
- The Copilot CLI must permit the single read-only
  `datadog(search_datadog_incidents)` capability; do not grant all tools or
  unrestricted approvals.
- Python dependencies used by the existing application and pytest environment.

## Validation

Run focused incident service and API tests:

```sh
python -m pytest tests/test_datadog_incidents.py tests/test_datadog_incidents_api.py
```

Run the full regression suite:

```sh
python -m pytest
```

Validate backend syntax and frontend ES modules using the repository's existing
validation commands, then run:

```sh
git diff --check
```

## End-to-end scenarios

1. Mock a valid provider response with multiple live incidents. Refresh, then
   read the cache and verify both Dashboard and Investigations use identical
   projections and freshness metadata.
2. Refresh successfully with an empty incident list. Verify `current` with
   zero incidents, not `unavailable`.
3. Replace one live result with a successful result that omits it. Verify it
   disappears from the current incident list and no local investigation file or review
   state changes.
4. Seed a good cache and force provider, schema-validation, and cache-write
   failures. Verify the prior incidents and success timestamp remain and the
   state is `stale`; without a prior cache verify `unavailable`.
5. Trigger simultaneous automatic and manual refreshes. Verify one provider
   call and a visible `refreshing` state.
6. Follow Create Investigation from an incident card. Verify only the title
   hint is prefilled and the existing Notebook URL, Preview, and explicit
   confirmation requirements remain.
