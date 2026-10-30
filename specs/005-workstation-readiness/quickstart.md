# Quickstart: Validate Workstation Readiness

## Prerequisites

- An approved NOC workstation with the existing application dependencies installed.
- A disposable test NOC root and probe directory; never use real operational data for automated
  tests.
- Python environment used by this repository (`.venv`).

Run focused validation after implementation:

```bash
.venv/bin/python -m pytest tests/test_readiness.py tests/test_readiness_api.py
```

Then run the existing suite:

```bash
.venv/bin/python -m pytest tests
```

## Validation record

Validated on 2026-10-29:

- Focused readiness coverage: `21 passed`.
- Complete suite: `119 passed` (one existing FastAPI/TestClient deprecation warning).
- Static checks: Python compilation, ES-module syntax parsing, and whitespace validation passed.

## Manual API validation

Start the application by the repository's normal development command, then request a valid shift:

```bash
curl -sS http://127.0.0.1:8000/api/readiness/2026-10-29
```

Verify the response conforms to [the API contract](contracts/readiness-api.md):

1. It has one configuration result, independent NOC-data/cache/command/write results, and a
   separate liveness array.
2. `overallStatus` is `ready` only when all required capabilities are ready.
3. A responding liveness probe does not hide a failed write, command, cache, or NOC-data check.
4. No response field exposes an absolute user path, supplied environment value, credential, command
   output, or record content.

## Override and safety scenarios

Use an isolated shell/environment for each case:

1. With no `NOC_WEB_*` values, confirm existing default behavior is preserved.
2. Set one valid documented override and confirm the assessment identifies a valid configuration
   without revealing its value.
3. Set `NOC_WEB_NOC_ROOT` to an empty, relative, or unsafe value. Confirm HTTP 422, no checks or
   liveness probes, no fallback to the default root, and a generic corrective action.
4. Make a cache exactly its configured maximum age, then older. Confirm each is not ready; make it
   younger and confirm it is ready. Repeat independently for each configured source.
5. Simulate a command missing, non-executable, timed out, or returning failure. Confirm a
   command-specific not-ready result and no raw stderr.
6. Use a destination that can be inspected but cannot accept the exclusive probe. Confirm liveness
   or reachability can remain available while write capability is not ready; confirm no existing
   file changes and a successful probe file is removed.
7. Use a compatible existing ticket/cache record and an incompatible one. Confirm the former is
   read unchanged and the latter is explicitly not ready with no conversion.

## Platform checks

- **Windows**: Run the application and its command catalog in Windows; use documented Windows
  absolute paths. Validate the exclusive write probe against the approved Windows destination.
- **WSL**: Run the application and command catalog in WSL; use Linux absolute paths and validate
  its Linux permission behavior. Do not pass a Windows path for automatic conversion.

See [data-model.md](data-model.md) for result semantics and
[contracts/readiness-api.md](contracts/readiness-api.md) for client behavior. Passing readiness
does not authorize an operational action: use the existing immediately preceding confirmation for
every state-changing workflow.
