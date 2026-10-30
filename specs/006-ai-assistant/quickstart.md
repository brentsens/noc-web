# Quickstart: Validate Bounded NOC AI Assistant

## Prerequisites

Use the repository virtual environment and pytest's isolated NOC root. Automated tests mock
subprocess execution and inject a deterministic provider callable; never use real NOC data,
provider credentials, live inference, noc-inv, or Datadog in automated tests. For local assistant
use, install and authenticate the GitHub Copilot CLI using its upstream instructions. NOC Web uses
that existing CLI session by default and stores no credentials.

## Focused automated validation

```bash
./.venv/bin/python -m pytest tests/test_assistant.py tests/test_assistant_api.py \
  tests/test_ai_reports.py \
  tests/test_investigations.py tests/test_safety.py tests/test_dashboard.py \
  tests/test_status.py tests/test_tickets.py tests/test_frontend_modules.py
node --input-type=module --check < frontend/js/workflow-context.js
```

Expected: all selected tests pass. Add contract/static tests for the assistant page and shared API
client if those tests are housed in an existing test module.

Cover: URL shift isolation and invalid/missing submit context; pre-submit provider disclosure;
minimum safe evidence only; cached Jira queue inclusion without refresh and cache freshness/error
representation; Local NOC Tracking, investigation, Shift Notes, Dashboard, Status, and readiness
source isolation; source-grounded facts distinct from existing operator-reviewed findings and
AI-generated observations/recommendations; insufficient/stale/malformed/conflicting evidence;
out-of-scope and prompt-injection limits; each prohibited action; no direct Datadog invocation;
routes that preserve existing confirmation; provider/evidence/schema failure isolation; no
prompt/context/raw-evidence/provider-output persistence or logging; successful predefined-action
report creation, collision and shift isolation, report-save failure, read-only viewing; and
regression behavior for features 001–005.
Also cover the Copilot CLI adapter's missing/authentication/timeout/non-zero/malformed paths,
temporary-file cleanup, fixed argument list, unavailable-tools filter, and all four AI Actions.

## Manual validation

1. Serve NOC Web with a non-production NOC root and open the assistant entry page with
   `?shift=2026-10-29`. Verify the visible workflow context, disclosure, advisory-only label, and
   no submit button enabled before disclosure acknowledgement.
2. Ask a supported situation question. Verify source-grounded Facts, operator-reviewed
   investigation findings, AI observations, Recommendations, evidence references, and limitations
   are visibly separate. Confirm no raw noc-inv/notebook content is displayed and no Jira refresh
   occurs. The default provider runs `copilot --trust-folder --available-tools --silent -p
   <fixed prompt>` from a private temporary directory; only `@context.json` contains the bounded
   question and selected-shift context. No tools or automatic approvals are enabled.
3. Navigate to an assistant-relevant view and back. Verify the same shift appears in every URL;
   use another shift and verify only that shift's bounded context is used. Use invalid/absent
   context at submit and verify no substitute shift answer is sent.
4. Simulate one unavailable/stale/malformed/conflicting evidence source. Verify it is named as a
   limitation while independent selected-shift evidence and all normal pages remain usable.
5. Request ticket creation, write/edit/close, refresh, sync, a command, Datadog, and an external
   query. Each must state nothing changed and offer only safe review/navigation. Follow a routed
   existing action and confirm its normal immediate confirmation remains required.
6. Simulate missing CLI, an unauthenticated session, timeout, non-zero exit, and invalid structured
   output. Verify a clear unavailable limitation, no success-looking answer, no raw error text,
   temporary-context cleanup, and continued Dashboard/Tickets/Investigations/Status usability.
7. Complete a predefined AI Action and verify one validated `ai-*.md` advisory report appears
   immediately in Recent AI Reports and opens in the read-only viewer. Verify it contains the
   selected shift/action/provider/status, normalized result categories, source/freshness status,
   and limitations, but no prompt, temporary context, raw provider output, credentials, tokens, or
   raw evidence. Verify generic assistant questions remain transient and report-save failure keeps
   the on-screen response while showing a separate warning.
8. Complete and fail requests, then inspect the isolated NOC root, application test logs, browser
   local/session storage, and network calls. Verify no prompt, raw evidence, or provider output is
   persisted/logged by NOC Web. Verify the provider disclosure remains qualified: provider-controlled
   handling may apply and is not asserted absent.

See [data-model.md](data-model.md) and [assistant-api.md](contracts/assistant-api.md).
