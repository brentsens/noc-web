# Release Contract

## Stable assets

For tag `vX.Y.Z`, GitHub Releases publishes exactly:

| Asset | Required name |
|---|---|
| Application archive | `noc-web-vX.Y.Z.tar.gz` |
| Checksum record | `noc-web-vX.Y.Z.sha256` |

The checksum record contains the SHA-256 digest and exact archive filename.
The platform publishes provenance for the exact archive separately from release
assets.

## Consumer verification

Before extraction, Feature 012:

1. Confirms the requested tag and release asset names.
2. Downloads the archive and checksum over the release's immutable asset URL.
3. Confirms the archive digest matches the checksum record.
4. Verifies provenance for the archive, repository
   `brentsens/noc-web`, approved release-workflow identity, and tagged commit.
5. Rejects any mismatch without extracting or executing the archive.

No long-lived private key, credential, token, or secret is a consumer input.

## Release state

The public release is created only after the archive, checksum, and provenance
are valid. Any failed validation, packaging, checksum, attestation, or upload
is a terminal safe failure, not a partially successful release.
