# noc-inv Invocation Contract

`noc-inv` remains the authoritative investigation-generation workflow. NOC Web must not reimplement its investigation logic or retrieve Datadog evidence directly.

## Required non-interactive behavior

- Resolve the executable and working/storage locations from the approved Feature 005 configuration; do not hard-code workstation paths.
- Invoke a fixed command using an argument array with shell interpretation disabled.
- Use a dedicated non-interactive mode and a fixed set of input values: selected ISO shift, normalized investigation name, exact validated Notebook URL, and a server-generated output/staging location.
- Treat each operator value as one data value; do not accept arbitrary options, commands, executable paths, or shell syntax from the request.
- Use the configured bounded `NOC_WEB_INVESTIGATION_TIMEOUT_SECONDS` timeout (default 300 seconds, maximum 900 seconds) and clean up temporary context on every exit.
- Preserve the configured authenticated Copilot CLI and Datadog MCP environment; do not pass credentials through request values or browser responses.
- Write generated output only to the server-selected staging location and never overwrite an existing investigation.
- Return enough controlled status for NOC Web to distinguish successful execution, unavailable dependency, timeout, and failure; never expose raw stdout/stderr, prompts, credentials, tokens, or filesystem diagnostics.

The required argument sequence is:

```text
[configured_noc_inv, "--non-interactive",
 "--shift-date", validated_shift_date,
 "--name", normalized_name,
 "--notebook-url", exact_notebook_url,
 "--output-dir", server_generated_staging_directory]
```

Only the executable path and staging directory come from trusted server configuration/request handling. No request field may add, remove, or reorder options; all operator-entered values are validated and passed as single argument values.

The current NOC Web repository readiness-probes `noc-inv` but does not define its invocation syntax. The implementation must add or use the safe non-interactive contract at the `noc-inv` boundary. If the configured command does not support that contract, NOC Web must fail closed with an unavailable result; it must not automate an interactive prompt or TTY.

## Output handoff

Generated output must preserve the selected shift, normalized name, exact FINAL Notebook URL, and evidence provenance. NOC Web validates the output before publishing it to the existing shift-scoped investigation store. Safe malformed output may be retained as `needs_review`; raw provider diagnostics and temporary Copilot context must not enter the published record or handover.
