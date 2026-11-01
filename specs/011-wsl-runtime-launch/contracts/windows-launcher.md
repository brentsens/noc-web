# Windows Launcher Contract

## Installed artifact

Setup creates or updates one current-user Windows shortcut named exactly
`SESAMI NOC Operations`. By default it is placed on the current user's Desktop;
an explicitly configured per-user shortcut folder may replace that location.
The installer resolves the known-folder path through Windows APIs and writes
the same shortcut path on every rerun.

Only the exact current-user Desktop path returned by
`Environment.GetFolderPath("DesktopDirectory")` is trusted when it is a
reparse point, including a OneDrive-redirected Desktop. A configured alternate
shortcut destination that is a reparse point is rejected. LocalAppData
installation and launcher paths retain their existing conservative
reparse-point checks. The installer runs on Windows PowerShell 5.1, with helper
functions defined or loaded before first invocation. An empty result from the
Desktop known-folder API is a safe categorized installation failure.

The shortcut launches the installed hidden Windows Script Host wrapper. The
wrapper and its credential-free configuration identify the exact configured
WSL distribution and Linux operator, localhost application URL, and bounded
health timeout. Neither the `.lnk` nor its arguments/configuration contains
credentials, tokens, or authentication material. The wrapper resolves the
Windows `wsl.exe` executable and Windows-quotes each configured command-line
argument: distribution, Linux user, Python path, launcher path, runtime
configuration path, URL, and timeout.

## Launch sequence

1. Invoke the resolved Windows `wsl.exe` through synchronous,
   hidden `WScript.Shell.Run`, using explicit distribution and user targeting.
   Do not rely on the current default distribution or host executable search
   path.
2. Request `systemctl --user start noc-web.service`; systemd start is
   idempotent and reuses an active service.
3. If WSL invocation or service start fails, show a concise error and exit.
4. Poll `GET <applicationUrl>/api/health` with bounded per-request and overall
   timeouts. The default total wait is 60 seconds.
5. On a healthy response, ask Windows to open the configured `http://` URL
   through its default browser handler, then exit.
6. On timeout, unhealthy response, or browser launch error, report the failure
   without opening a misleading URL or leaving a terminal process open.

No launcher step calls `wsl --shutdown`, modifies the distribution's default
user, installs external dependencies, or changes Jira, Datadog, email, or NOC
operational state.

## Failure results

The user-facing failure categories are verified WSL unavailable, verified
configured-distribution unavailable, user service unavailable, health timeout,
browser launch failure, and `WINDOWS_LAUNCH_EXECUTION_FAILED`. The final
category applies when `WScript.Shell.Run` raises an invocation error or returns
an unexpected result such as `-1`; it must not be presented as WSL or
distribution unavailability. Messages may include the safe category and
recovery hint only; raw `wsl.exe`, systemd, PowerShell, or subprocess output
is not displayed or persisted. Shortcut installation failures retain the
generic `SHORTCUT_INSTALL_FAILED` result and add an allowlisted safe reason
category; raw exception text is never included.

Where Windows Script Host is available, automated regression coverage executes
the generated VBScript through `cscript.exe` and the installed hidden
`wscript.exe` path. It verifies successful invocation of the known-good WSL
command, argument-boundary safety, no persistent console, and distinct safe
classification of the `-1`/unexpected-result boundary.
