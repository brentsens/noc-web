# Quickstart: Datadog Investigation Creation

**Feature**: [spec.md](spec.md)
**Plan**: [plan.md](plan.md)
**Contracts**: [contracts/investigations-api.md](contracts/investigations-api.md), [contracts/noc-inv-invocation.md](contracts/noc-inv-invocation.md)

## Prerequisites

- Use the repository's configured Python environment and local NOC Web settings.
- Tests must use temporary storage and a mocked `noc-inv` executable; do not use real NOC records, network services, Copilot authentication, Datadog MCP, or credentials.
- A deployed workstation must have the configured non-interactive `noc-inv` contract, Copilot CLI, and writable investigation storage for a real creation workflow.
- `NOC_WEB_INVESTIGATION_TIMEOUT_SECONDS` bounds generation (default 300 seconds; maximum 900 seconds), independently of short readiness command probes.

## Focused regression

Run the investigation creation, output-validation, and downstream-gating tests:

```bash
pytest -q tests/test_investigation_creation.py tests/test_investigation_generation.py tests/test_investigation_output_validation.py tests/test_investigations.py tests/test_readiness.py tests/test_end_shift.py tests/test_handover.py tests/test_assistant.py tests/test_frontend_modules.py
```

Expected: valid preview makes no files and starts no process; only a confirmed request invokes the mocked command; invalid values, conflict, unavailable command, timeout, malformed output, and provenance mismatch return controlled states; only reviewed concise findings reach downstream projections; frontend modules import successfully.

## Full regression and repository checks

```bash
pytest -q
git diff --check
```

Expected: the full existing regression suite passes and the diff has no whitespace errors.

## Browser workflow smoke

Run the application using the repository's normal local development procedure, open Investigations with a validated selected shift, and verify:

1. The existing list/detail and Review/Reject behavior remains available.
2. The create form shows the selected shift; invalid or missing shift context blocks preview.
3. Preview displays the normalized name, exact Notebook URL, logical destination, generator/review notice, and no-Jira/no-Datadog-modification statement; it does not call the create endpoint, execute a command, fetch the URL, or create files.
4. Cancel has no side effects. The final confirmation names the exact shift, normalized investigation, and URL.
5. After confirmed mocked creation, the list refresh selects the record and distinguishes generation, validation, provenance, review, and refresh state.
6. A valid generated record remains pending review; malformed retained output is visible as needing review and excluded from handover content.
7. No raw command diagnostics, credentials, temporary Copilot context, or Notebook-fetch response is exposed; the generated advisory record is visible locally, and no operational context is sent to external URLs.
