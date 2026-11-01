# Bootstrap Installer Contract

## Package contract

The release artifact is named `SESAMI-NOC-Operations-Setup.exe`. It displays
only the approved SESAMI NOC Operations branding and contains the bootstrap
manifest, verification key, verifier, bootstrap scripts, and generated icon.
It contains no operator authentication or NOC operational data.

## Result categories

The Windows bootstrap returns one safe terminal category:

| Category | Meaning | Next action |
|---|---|---|
| `BOOTSTRAP_READY` | Verified release handed off to Feature 011 and core health succeeded. | Launch SESAMI NOC Operations. |
| `WSL_SETUP_REQUIRED` | WSL is missing, disabled, or unsupported. | Follow guided platform setup. |
| `DISTRIBUTION_SETUP_REQUIRED` | Approved Ubuntu distribution is absent or unsupported. | Follow guided distribution setup. |
| `RUNTIME_SETUP_REQUIRED` | Required WSL runtime/systemd prerequisite is unavailable. | Correct the stated prerequisite. |
| `SOURCE_VERIFICATION_FAILED` | Release signature, identity, checksum, or archive validation failed. | Obtain a current approved package/release. |
| `CONFIRMATION_DECLINED` | Operator declined a workstation-changing action. | Rerun and approve the stated change if desired. |
| `PERMISSION_REQUIRED` | Required operator authorization was not available. | Follow the safe permission guidance. |
| `FEATURE011_HANDOFF_FAILED` | Existing managed-runtime installer did not complete. | Use the Feature 011 safe result and corrective guidance. |
| `DEPENDENCY_SETUP_REQUIRED` | Optional tool install/authentication/configuration remains incomplete. | Follow per-tool setup guidance; core NOC Web may still be ready. |

Raw command output, credentials, token values, release archive contents, and
authentication material are never included in this contract.

## Bootstrap sequence

1. Validate package manifest and inspect WSL/distribution/runtime prerequisites.
2. Guide and exit for missing platform prerequisites; do not initiate WSL or
   Ubuntu installation.
3. Resolve the current verified installation. If an update is available, show
   its version and request confirmation.
4. Download release archive, checksum manifest, and signature to a temporary
   per-user location. Verify signature, release identity, checksum, and archive
   paths before extraction.
5. Atomically stage verified content at the fixed per-user WSL installation
   root, preserving the previous verified release until handoff succeeds.
6. Invoke the staged Feature 011 installer and consume its safe health,
   service, launcher, and shortcut result.
7. With separate confirmation, provision only tool artifacts listed in the
   verified release manifest; never sign in or migrate identity.
8. Request the existing Feature 011 readiness assessment and present each
   optional result independently.

## Idempotence and ownership

Bootstrap owns its record, temporary downloads, verified release staging, and
package artifacts. Feature 011 owns the managed service, runtime configuration,
launcher, health wait, controlled PATH, and shortcut. Neither bootstrap nor
Feature 011 may delete NOC data or external authentication. A rerun repairs
the installed verified release by default and creates no duplicate repository,
runtime, service, launcher, or shortcut.
