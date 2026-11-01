# Implementation Plan: Trusted Release Pipeline

**Branch**: `013-trusted-release-pipeline` | **Date**: 2026-11-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/013-trusted-release-pipeline/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Publish a verified, immutable NOC Web source archive only from a valid version
tag. The release workflow validates the tagged checkout, creates a controlled
archive and checksum, generates platform-backed provenance for the final
archive, then publishes both named release assets. Feature 012 verifies the
checksum and provenance against the exact release workflow before staging.

## Technical Context

**Language/Version**: GitHub Actions YAML; Bash; Python 3.10+ application tests.

**Primary Dependencies**: GitHub Actions, GitHub Releases, GitHub artifact
attestations, `gh` CLI, existing pinned Python dependencies.

**Storage**: GitHub release assets and attestations; ephemeral runner workspace
only. No persistent release secrets or operator data.

**Testing**: Existing full pytest suite, workflow/static release-policy tests,
archive-content tests, checksum/provenance verification, and manual first
release verification.

**Target Platform**: GitHub-hosted Linux runner; GitHub release consumers,
including the Feature 012 Windows/WSL bootstrap.

**Project Type**: CI/CD release pipeline for the existing web application.

**Performance Goals**: Publish a validated release within 15 minutes under
normal GitHub service availability; no artifact is public before all
verification stages complete.

**Constraints**: Tag-only `vX.Y.Z`; least-privilege token permissions;
keyless short-lived identity; fixed archive/checksum names; no archive input
outside the tagged checkout; fail closed on all validation or publishing
errors.

**Scale/Scope**: One repository and one release pair per accepted version tag;
this feature supplies Feature 012 application-release trust inputs, not
noc-tools distribution artifacts.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate |
|---|---|
| I. Preserve Operational Data Integrity | Pass: release input is the exact tagged checkout; archives exclude operator data and local runtime state. |
| II. Fail Safely and Explain Failures | Pass: every validation, archive, checksum, attestation, and publication stage stops release publication on failure. |
| III. Maintain API and UI Contract Consistency | Pass: the release naming and verification contract is documented for Feature 012 consumers. |
| IV. Test Operational Workflows | Pass: archive and workflow checks use fixtures; the full application suite runs before publish; first release is independently verified. |
| V. Prefer Simple, Observable Changes | Pass: one tag workflow produces one archive/checksum pair plus platform provenance. |
| VI. Require Deliberate Operational Execution | Pass: a release requires an explicit protected version tag; no NOC workflow or external-state action is automated. |

No pre-design gate failures or exceptions.

## Project Structure

### Documentation (this feature)

```text
specs/013-trusted-release-pipeline/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)
```text
.github/workflows/
└── release.yml
scripts/release/
├── build-archive.sh
├── verify-release.sh
└── verify-first-release.sh
tests/
└── test_release_pipeline.py
packaging/windows/
└── bootstrap-manifest.json             # Feature 012 consumer contract update
```

**Structure Decision**: Keep release assembly and verification scripts
separate from application code; the workflow only orchestrates those scripts.
Feature 012 consumes release asset names and attestation identity but remains
the owner of local bootstrap behavior.

## Constitution Check (Post-Design)

| Principle | Result |
|---|---|
| I. Preserve Operational Data Integrity | Pass: archive allowlist and tagged checkout isolate release content from operational data. |
| II. Fail Safely and Explain Failures | Pass: draft creation occurs only after test, archive, checksum, and attestation success; publication is the final state transition. |
| III. Maintain API and UI Contract Consistency | Pass: Feature 012 consumes the versioned artifact contract documented in `contracts/release-contract.md`. |
| IV. Test Operational Workflows | Pass: workflow policy and archive filtering are regression-tested; first release requires independent verification. |
| V. Prefer Simple, Observable Changes | Pass: native platform attestations provide provenance instead of managed signing infrastructure. |
| VI. Require Deliberate Operational Execution | Pass: protected explicit tags control publication and release scripts do not touch NOC state. |

Post-design gates pass. No exception is required.
