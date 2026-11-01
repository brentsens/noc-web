# Data Model: Fresh Workstation Bootstrap Installer

## Bootstrap Installation Record

Credential-free per-user state owned by Feature 012. It is separate from NOC
data and Feature 011 runtime configuration.

| Field | Constraints |
|---|---|
| `schemaVersion` | Supported positive version; unknown versions fail without replacement. |
| `releaseId` | Verified immutable application release identifier. |
| `releaseVersion` | Verified version presented before an update confirmation. |
| `repository` | Exact approved GitHub repository from the package bootstrap manifest. |
| `installRoot` | One validated per-user WSL application location; never an unsafe root, traversal path, or untrusted symlink. |
| `archiveSha256` | SHA-256 verified against the signed release manifest. |
| `state` | `preflight`, `awaiting_confirmation`, `staging`, `handoff`, `ready`, or a safe failure state. |
| `lastResult` | Safe non-secret category only; never raw command output, release contents, or credentials. |
| `updatedAt` | UTC timestamp. |

Transitions proceed only forward after validation:
`preflight → awaiting_confirmation → staging → handoff → ready`. A failed
transition preserves the last verified installation and records a safe failure
category.

## Source Verification Record

Non-secret evidence created for every acquired release before it can become
staged.

| Field | Constraints |
|---|---|
| `releaseId` | Matches the requested approved release. |
| `assetName` | Exact expected release archive name. |
| `manifestSha256` | Hash of the downloaded checksum manifest. |
| `archiveSha256` | Hash of the downloaded release archive. |
| `signatureVerified` | Boolean; must be true before extraction. |
| `archiveValidated` | Boolean; must be true after entry/path validation. |
| `verifiedAt` | UTC timestamp. |

No URL query credentials, signature payload, or raw verifier output is
persisted.

## Prerequisite Assessment

A transient result for one bootstrap prerequisite.

| Field | Constraints |
|---|---|
| `id` | Stable value: `wsl`, `distribution`, `systemd`, `runtime`, `source`, `permission`, or `confirmation`. |
| `status` | `ready`, `setup_required`, or `unavailable`. |
| `impact` | Safe operator-facing effect. |
| `correctiveAction` | Safe next step; platform setup instructions are guide-only. |
| `required` | Boolean; optional tools are never core blockers. |

## Dependency Provisioning Result

A transient, non-secret result for Atlas, Copilot CLI, Microsoft 365 CLI,
Datadog MCP, or noc-tools.

| Field | Constraints |
|---|---|
| `id` | Stable external capability identifier shared with Feature 011 readiness. |
| `distributionStatus` | `available`, `not_available`, `installed`, or `failed`. |
| `authenticationStatus` | `not_required`, `setup_required`, `ready`, or `unavailable`. |
| `confirmed` | Boolean indicating operator confirmation before a workstation-changing install. |
| `sourceVerified` | Boolean; required before executing a provisioned artifact. |
| `guidance` | Safe corrective guidance with no authentication material. |

## Bootstrap Manifest

A package-bundled, versioned non-secret policy document.

| Field | Constraints |
|---|---|
| `applicationRepository` | Exact approved GitHub repository. |
| `releasePublicKey` | Identifier for the bundled verification key. |
| `releaseAssets` | Expected application archive, checksum manifest, and signature names. |
| `targetDistribution` | Exact approved Ubuntu distribution identity. |
| `toolEntries` | Optional per-tool version, source, checksum, target location, and compatibility range. |
| `brandingAsset` | Must identify only `assets/windows/sesami-noc-operations.png`. |

Manifest validation rejects unknown schema versions, unapproved repositories,
missing hashes, unsafe paths, and tool entries outside the verified release
compatibility range.
