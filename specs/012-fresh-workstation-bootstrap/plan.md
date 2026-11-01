# Implementation Plan: Fresh Workstation Bootstrap Installer

**Branch**: `012-fresh-workstation-bootstrap` | **Date**: 2026-11-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from
`specs/012-fresh-workstation-bootstrap/spec.md`

## Summary

Deliver a signed Windows setup executable that can bootstrap a fresh supported
workstation without an existing NOC Web checkout. The package guides WSL and
Ubuntu platform setup, verifies an approved signed GitHub release and its
SHA-256 manifest before staging it in a fixed per-user WSL location, then
delegates all managed runtime, health, launcher, localhost, and shortcut
behavior to Feature 011. Tool provisioning is manifest-controlled, confirmed
by the operator, credential-free, and separate from authentication.

## Technical Context

**Language/Version**: Windows PowerShell 5.1 bootstrap host; Bash and Python
3.10+ inside WSL; Inno Setup 6 packaging definition.

**Primary Dependencies**: Existing Feature 011 installer and runtime, Windows
WSL commands, a bundled release-signature verifier, Inno Setup, and the
existing pinned NOC Web Python requirements.

**Storage**: A per-user Windows bootstrap record and a credential-free
per-user WSL bootstrap record; verified release staging under one fixed
operator WSL application location. Existing Feature 011 runtime configuration,
service files, launcher files, shortcut, and NOC operational data remain
Feature 011-owned.

**Testing**: Pytest unit/integration tests for release verification,
provisioning manifest validation, confirmation and failure classification, and
Feature 011 handoff; Windows PowerShell 5.1 package/bootstrap tests; clean
Windows/WSL acceptance with no checkout, runtime, or shortcut; full pytest and
`git diff --check`.

**Target Platform**: Windows 10/11 with supported WSL2 Ubuntu; Windows
PowerShell 5.1; an unprivileged WSL operator and systemd-enabled distribution.

**Project Type**: Windows desktop setup package plus Windows/WSL bootstrap
scripts that provision the existing local web application.

**Performance Goals**: Core clean-workstation bootstrap completes within 20
minutes excluding operator-controlled authentication; all subprocess,
download, verification, and health operations have bounded deadlines.

**Constraints**: The package is named `SESAMI-NOC-Operations-Setup.exe` and
uses only `assets/windows/sesami-noc-operations.png` for its multi-resolution
ICO. Release archives, checksum manifests, and signatures must verify before
execution. Platform WSL/Ubuntu setup is guide-only. Application replacement
and optional tool installation require explicit confirmation. No credentials,
interactive PATH inheritance, or unapproved tool source may enter generated
files, logs, or process environments. Atlas uses only the existing trusted
`/home/linuxbrew/.linuxbrew/Homebrew/bin` service location; bootstrap must not
derive or inherit a broader Linuxbrew, interactive-shell, or Windows PATH.

**Scale/Scope**: One operator and one approved WSL Ubuntu distribution per
installation. The feature adds bootstrap acquisition and provisioning only; it
does not replace Feature 011 runtime ownership or introduce fleet management.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate |
|---|---|
| I. Preserve Operational Data Integrity | Pass: bootstrap writes only application-owned staging, records, and package files; it validates target paths and preserves NOC data, valid runtime configuration, and authentication. |
| II. Fail Safely and Explain Failures | Pass: every prerequisite, source, signature, checksum, confirmation, tool, Feature 011 handoff, health, and readiness failure has a bounded, safe category with no success-shaped fallback. |
| III. Maintain API and UI Contract Consistency | Pass: Feature 012 reuses the existing Feature 011 readiness response and page; any bootstrap status contract changes update backend and UI together. |
| IV. Test Operational Workflows | Pass: tests use temporary roots and stubs, validate release/manifests and no-credential behavior, and require clean Windows/WSL acceptance without real operational data. |
| V. Prefer Simple, Observable Changes | Pass: a thin bootstrap hands off to Feature 011 instead of duplicating its service, launcher, health, or shortcut implementation. |
| VI. Require Deliberate Operational Execution | Pass: platform setup is guide-only; application replacement and tool installation require explicit confirmation; bootstrap does not authenticate identities or trigger NOC mutations. |

No pre-design gate failures or constitution exceptions.

## Project Structure

### Documentation (this feature)

```text
specs/012-fresh-workstation-bootstrap/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
└── services/
    └── dependency_readiness.py
scripts/
├── bootstrap/
│   ├── acquire_release.py
│   ├── provision_dependencies.py
│   └── release_manifest.py
└── windows/
    ├── bootstrap-install.ps1
    ├── bootstrap-status.ps1
    └── install-shortcut.ps1             # Feature 011, reused unchanged
packaging/windows/
├── SESAMI-NOC-Operations-Setup.iss
├── bootstrap-manifest.json
├── release-public-key.txt
└── sesami-noc-operations.ico
assets/windows/
└── sesami-noc-operations.png
tests/
├── test_bootstrap_release.py
├── test_bootstrap_provisioning.py
├── test_bootstrap_handoff.py
└── windows/
    └── test_bootstrap_acceptance.ps1
```

**Structure Decision**: Keep Windows package definition and bootstrap resources
under `packaging/windows/`; place Windows orchestration under
`scripts/windows/` and WSL release/provisioning logic under
`scripts/bootstrap/`. Feature 011 files remain their owner-defined boundary
and are called, not copied.

## Constitution Check (Post-Design)

| Principle | Result |
|---|---|
| I. Preserve Operational Data Integrity | Pass: the bootstrap ownership boundary excludes NOC data and authentication, and release replacement is staged and verified before an explicit confirmed handoff. |
| II. Fail Safely and Explain Failures | Pass: signed manifest verification and a stateful bootstrap record prevent execution of unverified content and surface resumable safe failure categories. |
| III. Maintain API and UI Contract Consistency | Pass: bootstrap adds no competing readiness UI; it uses Feature 011 readiness after handoff. |
| IV. Test Operational Workflows | Pass: manifest, confirmation, error, and handoff tests are isolated; a clean workstation suite verifies the packaged primary journey and rerun. |
| V. Prefer Simple, Observable Changes | Pass: a single package invokes a single bootstrap path, then delegates to Feature 011. |
| VI. Require Deliberate Operational Execution | Pass: the design distinguishes guide-only platform remediation, confirmed provisioning, and never-automated authentication. |

Post-design gates pass. No constitution exception is required.
