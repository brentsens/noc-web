# Quickstart: Fresh Workstation Bootstrap Installer

This guide validates Feature 012 on a disposable supported Windows and WSL
environment. It is not a development-machine migration guide.

## Clean acceptance baseline

Before beginning, use a Windows 10/11 test user and supported WSL2 Ubuntu
distribution with systemd enabled. Confirm all of the following are absent:

- NOC Web checkout at the Feature 012 target location.
- Feature 011 runtime configuration, `noc-web.service`, launcher, and shortcut.
- NOC operational data and third-party authentication.

Keep the approved `SESAMI-NOC-Operations-Setup.exe` package and its release
assets available. Do not copy any configuration or credentials from another
workstation.

## Core bootstrap

1. Start `SESAMI-NOC-Operations-Setup.exe` from Windows.
2. Confirm it reports WSL and approved Ubuntu readiness; if either is missing,
   verify it provides guide-only remediation and makes no platform change.
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

1. Run bootstrap with each optional tool absent and confirm its status is
   separate from core NOC Web success.
2. For every approved installed tool that requires identity, confirm bootstrap
   reports setup required and does not authenticate or import identity.
3. Authenticate only a test operator account through each tool's normal
   operator-controlled process. Run the existing readiness view and confirm
   statuses update independently.
4. For Atlas, confirm the trusted Linuxbrew deployment is used and readiness
   reports ready only for a usable authenticated session and approved site.
5. Inspect package, bootstrap records, runtime configuration, logs, and
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
