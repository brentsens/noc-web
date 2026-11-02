# Verified Release and Provisioning Manifest Contract

## Application release

The package bootstrap manifest fixes the approved GitHub repository, immutable
tag, archive name, checksum asset, archive SHA-256, and fully qualified GitHub
Actions signer workflow. A downloaded release is executable only when:

1. Its download URLs are derived only from the approved repository and tag.
2. Its published checksum asset names the expected archive and matches the
   manifest's SHA-256 trust anchor.
3. GitHub SLSA provenance verifies with `gh attestation verify`, the exact
   repository, `refs/tags/<tag>`, and the approved fully qualified signer workflow.
4. Archive entries are safe relative paths and contain the required Feature 011
   installer artifacts.

Failure of any condition is `SOURCE_VERIFICATION_FAILED`; bootstrap must not
extract, stage, or execute the archive.

## Tool provisioning entries

Each optional entry is versioned and includes:

| Field | Requirement |
|---|---|
| `tool` | One of `atlas`, `copilot`, `m365`, `datadogMcp`, or `nocTools`. |
| `version` | Immutable compatible release version. |
| `source` | Approved artifact location covered by the verified release policy. |
| `sha256` | Required artifact checksum. |
| `target` | Validated approved target location. |
| `requiresConfirmation` | Must be true for a workstation-changing install. |
| `readinessId` | Existing Feature 011 readiness capability identifier. |

Entries never include credentials, cookies, tokens, sessions, private URLs, or
identity configuration. Atlas entries target the Feature 011 trusted Linuxbrew
location. A missing entry produces setup guidance; it does not authorize an
alternative package source.
