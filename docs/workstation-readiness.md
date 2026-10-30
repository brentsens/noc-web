# Workstation readiness

`GET /api/readiness/YYYY-MM-DD` is a read-only preflight. It proves only the listed
capabilities; it never refreshes Jira, alters tickets or cache data, discovers credentials, or
authorizes a later action. Use the existing immediate confirmation for every state-changing
workflow after readiness succeeds.

## Configuration

When absent, the historical defaults are NOC root `Path.home() / "noc"`, command directory
`Path.home() / ".local" / "bin"`, probe directory equal to the NOC root, Jira cache age of 1800
seconds, and command timeout of 10 seconds. Only these variables are supported:

| Variable | Requirement |
|---|---|
| `NOC_WEB_NOC_ROOT` | Existing absolute NOC directory |
| `NOC_WEB_NOC_BIN` | Existing absolute command directory |
| `NOC_WEB_READINESS_PROBE_DIR` | Existing absolute directory within the resolved NOC root |
| `NOC_WEB_JIRA_CACHE_MAX_AGE_SECONDS` | Positive integer at most 86400 |
| `NOC_WEB_COMMAND_TIMEOUT_SECONDS` | Positive integer at most 60 |

An unset variable uses its default. A present blank, relative, malformed, unsafe, inaccessible,
conflicting, or out-of-range value is terminal: the API returns a redacted 422 assessment and
does not touch default or alternate data. It never includes values, paths, command output,
record content, credentials, or exceptions in a response or log.

## Checks and recovery

Readiness separately validates compatible local ticket records, the existing
`.jira-open-tickets.json` cache, each required non-destructive command, and approved write
capability. Cache is ready only when its age is strictly below its configured source maximum;
missing, malformed, naive-time, incompatible, or over-age cache is not ready. Restore cache only
through its normal confirmed workflow. Compatible record formats are read unchanged; incompatible
records are not converted and must be repaired through the normal workflow.

The write check exclusively creates a random tiny sentinel, flushes and syncs it, then removes
only that file. It never overwrites an operational file. If it fails, restore destination access,
capacity, or cleanup ability before retrying.

Liveness is a separate diagnostic: `available` means its explicitly configured read-only probe
responded, not that cache, commands, NOC data, or write capability are ready. `notConfigured`
causes no implicit network call. Follow the capability-specific corrective action rather than
treating liveness as authorization.

## Startup, dependency, and recovery guidance

Start the application with the repository's normal development command and use the Readiness page
or endpoint before a shift. Required command probes use the fixed command catalog in the configured
command directory and bounded `shell=False` invocation. Shut down the normal application process
after local validation; readiness starts no background process and stores no diagnostic record.

Back up existing NOC data before manually repairing it. To recover, restore compatible ticket or
cache data from the approved backup, correct the documented override, restore required commands,
or restore destination capacity/access. Never copy secrets into readiness settings or diagnostics.

## Windows and WSL

Run the app and commands in one environment. Native Windows requires Windows absolute paths and
Windows command entries; WSL requires Linux absolute paths and Linux commands. The server does
not translate `C:\...` to `/mnt/c/...`, infer mounted paths, or share a profile across environments.
The exclusive create/write/sync/delete probe is the portable write evidence on both platforms.

## Validation

Run focused readiness tests with:

```bash
.venv/bin/python -m pytest tests/test_readiness.py tests/test_readiness_api.py
```

Then run the full suite:

```bash
.venv/bin/python -m pytest tests
```
