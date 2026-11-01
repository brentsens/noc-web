# Quickstart: Trusted Release Pipeline

Use a disposable valid version tag on a non-production test commit before the
first real release.

1. Confirm the checkout is clean and its complete test suite passes.
2. Create and push a valid `vX.Y.Z` test tag.
3. Confirm the release process validates the tagged commit before publishing.
4. Inspect the published archive and checksum names against
   [release-contract.md](contracts/release-contract.md).
5. Verify the archive checksum, provenance identity, repository, workflow, and
   tagged commit before extraction.
6. List archive entries and confirm required bootstrap/runtime files are
   present and local data, credentials, virtual environments, caches, logs,
   and temporary content are absent.
7. Attempt altered archive and checksum fixtures; confirm verification fails
   before extraction.
8. For the first real release, record independent verification of every
   contract check before enabling Feature 012 release acquisition.

Failure at any step blocks publication or Feature 012 use; do not substitute a
manual archive or mutable branch.
