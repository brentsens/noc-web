# Research: Trusted Release Pipeline

## Decision 1: Use a valid-tag push as the only release trigger

**Decision**: The release workflow accepts only a push of a `vX.Y.Z` tag and
verifies that the checked-out commit is the tag's exact target before release
assembly.

**Rationale**: An explicit immutable version reference gives Feature 012 a
stable release identity and prevents a mutable branch from becoming a release.

**Alternatives considered**: Branch-triggered releases are mutable; manual
workflow dispatch alone lacks the required tag identity.

## Decision 2: Use platform keyless artifact attestations

**Decision**: Use GitHub's OIDC-backed artifact attestation for the final
archive, with narrowly scoped release permissions and no repository private
signing key.

**Rationale**: The attestation cryptographically binds the final archive
digest, repository, workflow, and source commit using a short-lived identity.

**Alternatives considered**: A checked-in private key violates the
requirements; a manually managed external signing service adds avoidable
operational complexity.

## Decision 3: Validate, hash, attest, then publish

**Decision**: Run all tests and archive checks first, calculate the checksum
for the final archive, attest that final archive, then create the public
release with archive and checksum assets.

**Rationale**: A failure at any stage stops before publication. Attesting the
final file prevents a consumer from validating a different intermediate.

**Alternatives considered**: Publishing before attestation creates a public
artifact with incomplete trust evidence.

## Decision 4: Assemble an allowlisted archive

**Decision**: Build the release only from explicit repository paths required by
Feature 011 and Feature 012, then reject excluded or unsafe entries.

**Rationale**: An allowlist is more reliable than attempting to enumerate all
possible local sensitive files and development artifacts.

**Alternatives considered**: Packaging the working directory risks including
virtual environments, credentials, operational data, or caches.

## Decision 5: Pin consumer verification identity

**Decision**: Feature 012 verifies the archive checksum and pins attestation
verification to this repository's release workflow identity and the requested
tagged release.

**Rationale**: It prevents another workflow or another repository from being
accepted solely because it has a valid platform attestation.

**Alternatives considered**: Verifying only an archive checksum cannot prove
the archive's producer or source identity.
