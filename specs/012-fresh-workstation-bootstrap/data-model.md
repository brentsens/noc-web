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
| `archiveSha256` | SHA-256 verified against the approved release checksum asset and manifest trust anchor. |
| `state` | `preflight`, `awaiting_confirmation`, `staging`, `handoff`, `ready`, or a safe failure state. |
| `lastResult` | Safe non-secret category only; never raw command output, release contents, or credentials. |
| `updatedAt` | UTC timestamp. |

Transitions proceed only forward after validation:
`preflight → awaiting_confirmation → staging → handoff → ready`. A failed
transition preserves the last verified installation and records a safe failure
category.

The state file is atomically serialized with exactly the fields above. It
contains no URLs, command output, credentials, or operator data. Before a
rerun changes application-owned content, it is classified without mutation as
`current`, `older`, `incompatible`, `interrupted`, `failed`, or `corrupt`.
`current` requires the exact approved release and a complete installed release;
an invalid record or incomplete installation is `corrupt`.

## Source Verification Record

Non-secret evidence created for every acquired release before it can become
staged.

| Field | Constraints |
|---|---|
| `releaseId` | Matches the requested approved release. |
| `assetName` | Exact expected release archive name. |
| `manifestSha256` | Hash of the downloaded checksum manifest. |
| `archiveSha256` | Hash of the downloaded release archive. |
| `provenanceVerified` | Boolean; GitHub SLSA provenance must verify the exact repository, tag ref, and approved signer workflow before extraction. |
| `archiveValidated` | Boolean; must be true after entry/path validation. |
| `verifiedAt` | UTC timestamp. |

No URL query credentials, signature payload, or raw verifier output is
persisted.

## Prerequisite Assessment

A transient result for one bootstrap prerequisite.

| Field | Constraints |
|---|---|
| `id` | Stable value: `wsl2`, `distribution`, `systemd`, `runtime`, `source`, `permission`, or `confirmation`. |
| `status` | `ready`, `setup_required`, or `unavailable`. |
| `impact` | Safe operator-facing effect. |
| `correctiveAction` | Safe next step; platform setup instructions are guide-only. |
| `required` | Boolean; optional tools are never core blockers. |

The detected `/etc/os-release` distribution family is bounded non-secret
diagnostic metadata. It determines whether missing packages can use the
Ubuntu-only approved provisioning path; it does not determine whether an
otherwise capable WSL 2 distribution can run NOC Web.

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
| `releaseAssets` | Exact approved repository, immutable tag, application archive, checksum asset, SHA-256, and fully qualified signer workflow. |
| `targetDistribution` | Exact approved Ubuntu distribution identity. |
| `toolEntries` | Optional per-tool version, source, checksum, target location, and compatibility range. |
| `brandingAsset` | Must identify only `assets/windows/sesami-noc-operations.png`. |

Manifest validation rejects unknown schema versions, unapproved repositories,
missing hashes, unsafe paths, and tool entries outside the verified release
compatibility range.
