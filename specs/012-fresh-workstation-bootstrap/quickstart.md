# Quickstart: Fresh Workstation Bootstrap Installer

This guide validates Feature 012 on a disposable supported Windows and WSL
environment. It is not a development-machine migration guide.

Feature 012 supports two installation frontends that share the same trusted
release engine:

1. **WSL-native** — `scripts/install-sesami.sh` (supported baseline / unsigned fallback)
2. **Windows EXE** — `SESAMI-NOC-Operations-Setup.exe` (wizard frontend; may need
   Authenticode or application-control approval)

Do not claim clean-machine acceptance for either frontend until it is executed
on a genuine clean workstation.

## Clean acceptance baseline

Before beginning, use a Windows 10/11 test user and a WSL2 distribution with
systemd enabled. Ubuntu is the supported distribution for automatic
prerequisite provisioning; another distribution may be used only when it
already satisfies the complete runtime capability contract. Confirm all of the
following are absent:

- NOC Web checkout at the Feature 012 target location.
- Feature 011 runtime configuration, `noc-web.service`, launcher, and shortcut.
- NOC operational data and third-party authentication.

Keep the approved release assets available. For the EXE path, also keep
`SESAMI-NOC-Operations-Setup.exe`. Do not copy any configuration or credentials
from another workstation. Do not use `curl | bash`.

The package policy must pin NOC Web `v1.0.4` and noc-tools `v1.0.1`. Both
archives must pass their pinned SHA-256, published checksum, and GitHub
attestation checks before extraction.

## Core bootstrap (WSL-native)

1. In WSL2, download `noc-web-v1.0.4.tar.gz` and `noc-web-v1.0.4.sha256`
   explicitly (browser or `gh release download`).
2. Verify SHA-256 and `gh attestation verify` with the pinned signer workflow
   and `refs/tags/v1.0.4`, or run
   `scripts/bootstrap/verify_bootstrap_bundle.sh` against those local files.
3. Extract the archive and run:
   `./scripts/install-sesami.sh --confirm-prerequisites --github-cli-approved --confirm-replacement --confirm-noc-tools`
4. Confirm WSL2, `/etc/os-release` family, non-root passwd home, systemd user
   services, Python 3.10+/venv/pip/CA, and gh attestation readiness. On Ubuntu,
   confirm remediation prompts for approved packages only. On another
   distribution, confirm capability guidance without apt.
5. Confirm Feature 011 creates the managed service and runtime configuration.
6. Confirm `~/.local/bin/sesami-noc-launch` exists and the Desktop shortcut
   targets Windows-owned `wsl.exe` with `--distribution` and `--exec` pointing
   at that launcher.
7. Launch **SESAMI NOC Operations** from Windows. Confirm health succeeds,
   the default browser opens `http://127.0.0.1:8000`, no Linux terminal remains,
   and a second launch reuses `noc-web.service` without duplicates.

## Core bootstrap (Windows EXE)

1. Start `SESAMI-NOC-Operations-Setup.exe` from Windows.
2. Confirm it reports WSL 2, the `/etc/os-release` distribution family,
   Python 3.10+, real venv/pip, CA/SSL, systemd user-service, and `gh`
   attestation readiness. On Ubuntu, verify only missing approved packages are
   shown with their exact command and an explicit confirmation. If gh is
   missing or lacks attestation support, verify its separate prompt identifies
   GitHub's official apt source, makes no identity change, and rechecks the
   capability. On another distribution, verify a missing capability produces
   guidance without apt.
3. Confirm any application staging or optional dependency installation prompt
   clearly identifies the proposed workstation change. Decline once and verify
   the safe declined result, then rerun and approve.
4. Confirm application release identity, signature, checksum, and archive
   validation succeed before Feature 011 is invoked.
5. Confirm Feature 011 creates the user service, runtime configuration,
   controlled service environment, and exactly one branded shortcut.
6. Launch **SESAMI NOC Operations**. Confirm local health succeeds before the
   browser opens and no terminal remains. Launch it again and confirm service
   reuse without a duplicate process.

## Dependency and identity validation

1. Begin with noc-tools absent. After core installation, explicitly confirm
   the optional noc-tools action; confirm it installs the approved compatible
   release at its managed non-checkout location and exposes `tix`, `noc-start`,
   `noc-status`, `noc-inv`, and `noc-handover`. Confirm
   `noc-inv --contract-version` prints `noc-inv-contract=1`.
2. Run bootstrap with each optional tool absent and confirm its status is
   separate from core NOC Web success.
3. For every approved installed tool that requires identity, confirm bootstrap
   reports setup required and does not authenticate or import identity.
4. Authenticate only a test operator account through each tool's normal
   operator-controlled process. Run the existing readiness view and confirm
   statuses update independently.
5. For Atlas, confirm the trusted Linuxbrew deployment is used and readiness
   reports ready only for a usable authenticated session and approved site.
6. Inspect package, bootstrap records, runtime configuration, logs, and
   shortcut arguments. Confirm no credentials, token values, session data,
   cookies, or raw subprocess output appear.

## Verification and rerun

Run focused bootstrap tests, Feature 011 runtime/readiness tests, then the
full repository test suite and `git diff --check`.

Rerun the package without a newer approved release and confirm it repairs or
reuses the installation without duplicates. Present a newer verified release
fixture; confirm its version is shown, declining preserves the prior verified
release, and approving updates only application-owned content while preserving
NOC data, valid runtime configuration, and operator authentication.
