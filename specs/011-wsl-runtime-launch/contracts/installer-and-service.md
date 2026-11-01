# Installer and Service Contract

## Installer entry point

`scripts/install.sh` is run by the current unprivileged WSL operator from the
expected NOC Web checkout or a validated release directory. It must not be
run as root.

The installer:

1. Validates source identity, Python compatibility, configured repository and
   workspace paths, port/URL consistency, and supported systemd user-service
   availability before replacing managed artifacts.
2. Creates or updates the NOC Web virtual environment from the pinned runtime
   requirements. External tools remain independently maintained.
3. Creates or reuses the versioned per-user runtime configuration. Existing
   valid selections are retained; invalid or unknown configurations fail
   without overwriting the original.
4. Writes the systemd user unit and runtime launcher configuration atomically,
   retaining a recovery copy before replacing owned files.
5. Renders each systemd value according to its directive syntax; generic
   shell-style quoting must not turn configured absolute paths into invalid
   values. Automated regression tests run
   `systemd-analyze --user verify <generated-unit>` and fail if the validator
   is unavailable or rejects the unit.
6. Ensures the user manager can run without an interactive login (using
   systemd linger where supported); if required authorization is not available,
   reports the exact setup blocker and does not install a root service.
7. Reloads the user manager, enables and starts `noc-web.service`, then checks
   `GET <applicationUrl>/api/health` with a bounded timeout.
8. Runs the shortcut installer under Windows PowerShell 5.1 and installs or
   updates exactly one Windows shortcut named `SESAMI NOC Operations` for the
   current Windows user. Helper functions are available before first use.
   An empty result from the Desktop known-folder API is a categorized failure;
   it is never used as a path.
   The exact path returned by
   `Environment.GetFolderPath("DesktopDirectory")` is trusted as the Desktop
   destination even when redirected through OneDrive and marked as a reparse
   point. This exception does not extend to arbitrary configured destinations;
   LocalAppData installation paths retain conservative reparse-point checks.
   Failure is reported with `SHORTCUT_INSTALL_FAILED` plus a safe categorized
   reason, never raw exception output.
9. Reports each external dependency separately without installing or
   authenticating it.

Success means all required runtime, service, health, and Windows shortcut
steps succeeded. Optional external dependency absence is reported but does not
fail core runtime installation. A failure is nonzero and names a safe
step/error code; it never includes raw subprocess output or credentials.

Setup/update owns only the NOC Web virtual environment (when configured as
NOC-Web-owned), its runtime configuration, service unit, launcher support
files, and the named shortcut. It never deletes or migrates `~/noc` records,
handover files, AI reports, Feature 009/010 data, or tool authentication.

Windows installer regression coverage executes the actual shortcut installer
under Windows PowerShell 5.1. It covers helper availability before invocation,
the OS-reported redirected Desktop reparse-point exception, rejection of an
arbitrary configured reparse-point destination, unchanged conservative
LocalAppData checks, and safe categorized failures.

## Systemd user unit

The unit is installed at
`$XDG_CONFIG_HOME/systemd/user/noc-web.service` or
`$HOME/.config/systemd/user/noc-web.service`.

Required properties:

- Runs in the current operator's user manager; no `User=root` or system unit.
- Uses the validated repository as `WorkingDirectory` and the selected
  virtual-environment Python interpreter.
- Invokes the service entry point as
  `python -m scripts.run_service --config <runtime-config>` from that
  repository working directory. Import resolution must not depend on shell
  activation or inherited `PYTHONPATH`.
- Binds Uvicorn to `127.0.0.1` and the validated port.
- Provides explicit `HOME` and a fixed `PATH` that includes `~/.local/bin`
  and `/home/linuxbrew/.linuxbrew/Homebrew/bin`, without serializing
  credential environment variables or inheriting interactive-shell or Windows
  PATH entries.
- Restarts on failure with bounded delay and start-rate limit.
- Uses normal systemd stop/signal handling and journal output.
- Does not start an alternate provider or modify external systems.
- Uses directive-specific systemd syntax; automated regression tests require
  `systemd-analyze --user verify` to accept the generated unit.

Automated service-context regression executes the generated unit's exact
`ExecStart` in a subprocess using the declared `WorkingDirectory` and
environment, after removing inherited `VIRTUAL_ENV` and `PYTHONPATH`. It
verifies startup passes the `backend` import boundary; importing
`run_service.py` inside the test process is insufficient. Neither this test
nor native unit verification completes T029. T029 remains open until the
actual workstation installer, managed service, health endpoint, and Windows
shortcut all succeed.

Regression coverage also verifies that a supported dependency placed in
`/home/linuxbrew/.linuxbrew/Homebrew/bin` is discoverable by the managed
service, while Windows PATH entries and unallowlisted interactive-shell paths
are absent.

Starting an already-active unit must be idempotent. A port conflict causes an
explicit startup failure, not a second listener or a success-shaped response.
T029 is a separate real workstation acceptance test of installed runtime and
Windows/WSL behavior.

## Service management and recovery

The documented operator commands are:

```text
systemctl --user status noc-web
systemctl --user restart noc-web
systemctl --user stop noc-web
systemctl --user start noc-web
journalctl --user -u noc-web
journalctl --user -u noc-web -f
```

Manual troubleshooting requires stopping the managed service first, then
running the same configured Python application on the same localhost/port.
Return to managed mode by stopping the manual process and starting the user
unit. The installer and documentation must identify a port already held by
another process.
