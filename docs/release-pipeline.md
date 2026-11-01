# Trusted release pipeline

Create a release only by pushing an immutable `vX.Y.Z` tag. The workflow runs
the complete test suite, creates `noc-web-vX.Y.Z.tar.gz` and
`noc-web-vX.Y.Z.sha256`, attests the final archive with GitHub's keyless
identity, then publishes both release assets.

Do not upload an archive manually, alter a published checksum, or add tokens,
credentials, sessions, private keys, operator data, local configuration, logs,
or virtual environments to a release. A failed stage publishes no release.

Before enabling Feature 012 acquisition for the first release, run:

```bash
scripts/release/verify-first-release.sh vX.Y.Z .github/workflows/release.yml
```

Record a successful result with the release change. A failure blocks Feature
012 release acquisition until it is corrected and reverified.
