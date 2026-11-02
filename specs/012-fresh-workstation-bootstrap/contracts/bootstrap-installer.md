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
| `DISTRIBUTION_SETUP_REQUIRED` | The selected WSL distribution cannot be started. | Follow guided distribution setup. |
| `RUNTIME_SETUP_REQUIRED` | Required WSL runtime/systemd prerequisite is unavailable. | Correct the stated prerequisite. |
| `SOURCE_VERIFICATION_FAILED` | Release signature, identity, checksum, or archive validation failed. | Obtain a current approved package/release. |
| `CONFIRMATION_DECLINED` | Operator declined a workstation-changing action. | Rerun and approve the stated change if desired. |
| `PERMISSION_REQUIRED` | Required operator authorization was not available. | Follow the safe permission guidance. |
| `FEATURE011_HANDOFF_FAILED` | Existing managed-runtime installer did not complete. | Use the Feature 011 safe result and corrective guidance. |
| `DEPENDENCY_SETUP_REQUIRED` | Optional tool install/authentication/configuration remains incomplete. | Follow per-tool setup guidance; core NOC Web may still be ready. |

Raw command output, credentials, token values, release archive contents, and
authentication material are never included in this contract.

## Bootstrap sequence

1. Validate package manifest and inspect WSL 2, the selected distribution's
   `/etc/os-release` family, and the complete runtime capability contract.
2. Any WSL 2 distribution may continue when Python 3.10+, real venv/pip
   bootstrap, Python SSL/CA support, systemd user services, and
   `gh attestation verify --help` all pass. For missing core Ubuntu packages
   only, show the exact approved command
   `sudo apt-get update && sudo apt-get install --yes <missing packages>` and
   require separate explicit operator confirmation before running it. Declining
   this prerequisite action returns `RUNTIME_SETUP_REQUIRED`. The
   allowed package set is `python3`, `python3-venv`, and `ca-certificates`;
   recheck every prerequisite after installation and before any release,
   noc-tools, or optional-integration action. Non-Ubuntu distributions never
   receive apt remediation: missing capabilities are reported safely instead.
   On Ubuntu only, missing `gh` or an installed `gh` without attestation
   support offers a separate confirmed action that downloads the official
   `https://cli.github.com/packages` signing key, configures that signed apt
   repository, then runs `apt-get update` and `apt-get install --yes gh`.
   It neither signs in nor reads authentication files, and rechecks
   `gh attestation verify --help` before acquisition.
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
   verified release manifest; never sign in or migrate identity. noc-tools
   checks its optional `bash`, `jq`, `timeout`, and `mktemp` capabilities
   before mutation; missing tools report setup-required and do not block core.
8. Request the existing Feature 011 readiness assessment and present each
   optional result independently.

## Idempotence and ownership

Bootstrap owns its record, temporary downloads, verified release staging, and
package artifacts. Feature 011 owns the managed service, runtime configuration,
launcher, health wait, controlled PATH, and shortcut. Neither bootstrap nor
Feature 011 may delete NOC data or external authentication. A rerun repairs
the installed verified release by default and creates no duplicate repository,
runtime, service, launcher, or shortcut.
