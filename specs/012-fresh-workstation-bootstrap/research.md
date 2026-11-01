# Research: Fresh Workstation Bootstrap Installer

## Decision 1: Build a signed Windows setup executable with Inno Setup

**Decision**: Package the Windows bootstrap as
`SESAMI-NOC-Operations-Setup.exe` using Inno Setup 6. Generate a
multi-resolution ICO exclusively from
`assets/windows/sesami-noc-operations.png`; sign the generated package in the
release pipeline.

**Rationale**: The operator needs one familiar Windows entry point on a
workstation with no NOC Web checkout. A native setup executable can carry the
bootstrap scripts, verifier, approved branding, and uninstall metadata without
requiring the operator to run source scripts manually.

**Alternatives considered**: A raw PowerShell script is not a standalone
package and creates execution-policy friction. A copied Feature 011 shortcut
does not acquire a release or establish platform prerequisites.

## Decision 2: Verify release artifacts before staging or executing them

**Decision**: A fixed, package-bundled bootstrap manifest identifies the
approved GitHub repository, release asset names, the signed checksum manifest,
and the release-verification public key. Bootstrap downloads release artifacts
to a temporary per-user location, verifies the manifest signature and archive
SHA-256, validates archive entries, then atomically stages the verified release
in the fixed WSL application location.

**Rationale**: A downloaded archive is untrusted until its signing authority,
declared identity, checksum, and archive shape are verified. Staging prevents a
failed or interrupted download from replacing an existing known-good release.

**Alternatives considered**: Executing an archive after an HTTPS download
alone does not meet the signed-release and fail-closed requirement. Cloning a
mutable branch violates deterministic acquisition and requires Git on the
fresh workstation.

## Decision 3: Keep WSL and Ubuntu setup guide-only

**Decision**: Bootstrap detects WSL2, the approved Ubuntu distribution, and
systemd readiness. It presents approved remediation instructions and exits
without initiating platform installation. After platform readiness, it asks
for confirmation before application replacement or optional tool provisioning.

**Rationale**: Installing WSL or a Linux distribution can require elevation,
restart, policy acceptance, and operator choice. Guided remediation respects
the explicit confirmation boundary while still producing a clear next action.

**Alternatives considered**: Silently running platform-install commands is a
consequential workstation change. Treating missing prerequisites as a generic
installation failure hides the corrective action.

## Decision 4: Delegate managed runtime ownership to Feature 011

**Decision**: After a verified release is staged, the WSL bootstrap invokes
the release's existing Feature 011 installer. It consumes only its safe result
and readiness contract; it does not render a second service unit, runtime
configuration, hidden launcher, health wait, or Desktop shortcut.

**Rationale**: Feature 011 already owns the service, localhost constraints,
launcher behavior, known-folder safety, and readiness. One owner avoids
divergent runtime behavior.

**Alternatives considered**: Duplicating Feature 011 setup in the package
would create incompatible service and shortcut ownership.

## Decision 5: Use a versioned provisioning manifest and separate identity

**Decision**: The verified NOC Web release includes a versioned provisioning
manifest that lists compatible, approved distribution artifacts for Atlas,
GitHub Copilot CLI, Microsoft 365 CLI, Datadog MCP components, and noc-tools.
For each entry, bootstrap validates the declared source and checksum, asks for
confirmation before installation, and reports guidance when no compatible
entry exists. It never imports or supplies authentication files.

**Rationale**: Tool installers and compatibility versions are release-specific.
A manifest makes allowed source selection auditable and avoids arbitrary
interactive PATH discovery. Existing Feature 011 readiness remains the source
of truth for authentication and usability.

**Alternatives considered**: Installing whatever a package manager happens to
find is non-reproducible. Treating installation as authentication would expose
or misrepresent operator identity.

## Decision 6: Treat update as a confirmed verified replacement

**Decision**: A rerun repairs or reuses the currently verified release by
default. If a newer verified release is available, bootstrap displays the
version and requires confirmation before staging and handing it to Feature
011.

**Rationale**: This preserves idempotence and data while preventing unexpected
application replacement.

**Alternatives considered**: Silent latest-version updates conflict with the
operator-confirmation requirement. A repair-only installer cannot fulfill the
approved upgrade flow.

## Platform caveat

The final clean-workstation acceptance run must use a supported Windows/WSL
environment that has no existing checkout, Feature 011 artifacts, shortcut,
NOC data, or credentials. Unit tests cannot substitute for package execution,
Windows known-folder behavior, or a fresh WSL distribution.
