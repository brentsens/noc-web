# Feature Specification: Fresh Workstation Bootstrap Installer

**Feature Branch**: `012-fresh-workstation-bootstrap`

**Created**: 2026-11-01

**Status**: Draft

**Input**: User description: "Create a standalone SESAMI NOC Operations
installer for a fresh supported Windows workstation that acquires NOC Web,
prepares its managed runtime and approved operational tools, and leaves
operator authentication separate and visible."

## Clarifications

### Session 2026-11-01

- Q: What approved source and verification authority must a fresh installer trust? → A: A signed GitHub release plus a published SHA-256 manifest.
- Q: Which prerequisite actions may the installer perform automatically after a clear confirmation, and which must always be guided-only? → A: Guide platform setup; confirm application/tool changes.
- Q: What source and version authority defines the approved noc-tools distribution for a fresh workstation? → A: A versioned NOC Web release manifest.
- Q: How should a normal rerun handle a newer approved NOC Web release? → A: Offer a verified update with confirmation; otherwise repair or reuse the current release.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bootstrap NOC Operations (Priority: P1)

An operator on a fresh supported Windows workstation runs
**SESAMI-NOC-Operations-Setup.exe**. The installer acquires an approved NOC
Web release, installs it in the operator's WSL environment, invokes Feature
011 runtime setup, and creates the branded Windows shortcut without requiring
manual cloning, terminal setup, or virtual-environment activation.

**Why this priority**: This is the minimum journey that makes NOC Operations
usable on a workstation that has no prior NOC Web checkout or runtime.

**Independent Test**: On a clean supported Windows and WSL environment with no
NOC Web checkout, Feature 011 runtime, or shortcut, run the installer and
confirm acquisition, runtime health, and exactly one branded shortcut.

**Acceptance Scenarios**:

1. **Given** a fresh supported workstation with WSL and the approved Ubuntu
   distribution available, **When** the operator starts the installer, **Then**
   it acquires and verifies the approved application source, installs it in the
   standard per-user location, and completes Feature 011 runtime setup.
2. **Given** the installation finishes, **When** the operator starts
   **SESAMI NOC Operations** from Windows, **Then** NOC Web opens only after
   local health succeeds and without requiring a manually opened WSL terminal.
3. **Given** the managed service is already healthy, **When** the operator
   starts the shortcut again, **Then** the existing service is reused and no
   duplicate application process is created.
4. **Given** the approved application source cannot be verified, **When** the
   installer attempts acquisition, **Then** it fails before executing the
   acquired content and shows a safe actionable diagnostic.

---

### User Story 2 - Understand Prerequisites and Readiness (Priority: P1)

An operator receives distinct, actionable results when WSL, the approved
distribution, supported runtime prerequisites, application acquisition, or
runtime setup cannot complete. After a successful application installation,
the existing readiness experience tells the operator whether each optional
operational integration is ready, needs setup, or is temporarily unavailable.

**Why this priority**: A bootstrap flow must not conceal a missing platform
requirement or confuse a missing integration with a failed application.

**Independent Test**: Vary each prerequisite and optional dependency on an
isolated test workstation and confirm a safe, specific result while unrelated
ready capabilities remain correctly reported.

**Acceptance Scenarios**:

1. **Given** WSL is missing, the approved distribution is missing, or a
   required runtime is unsupported, **When** the operator starts the installer,
   **Then** it identifies the exact condition and provides approved next
   steps without reporting installation as successful.
2. **Given** the core application installation succeeds but an optional
   integration needs authentication or configuration, **When** installation
   completes, **Then** NOC Web remains available and readiness reports that
   integration separately with safe corrective guidance.
3. **Given** an Atlas installation has a usable authenticated session and
   usable approved site access, **When** readiness runs, **Then** Atlas is
   reported ready without exposing authentication data.

---

### User Story 3 - Install Tools Without Migrating Identity (Priority: P1)

An operator can receive supported operational command-line tools where their
approved installers are available, while completing their own authentication
after installation. The bootstrap process never takes credentials, sessions,
cookies, tokens, or authentication files from another workstation or package.

**Why this priority**: Tool availability is needed for NOC workflows, but
operator identity and authorization must remain individual and controlled.

**Independent Test**: Run bootstrap with each supported tool absent and verify
that installation status and authentication-required status are distinguished;
inspect all generated artifacts to confirm no source credentials are present.

**Acceptance Scenarios**:

1. **Given** an approved tool installer is available and the operator
   authorizes installation, **When** bootstrap runs, **Then** it installs or
   configures the tool through the approved distribution channel and reports
   its readiness independently.
2. **Given** a newly installed tool requires operator authentication, **When**
   bootstrap completes, **Then** it reports setup required and directs the
   operator to authenticate their own account without launching an
   unauthorised identity action.
3. **Given** a tool cannot be installed or its approved source is unavailable,
   **When** bootstrap completes, **Then** NOC Web core setup remains usable
   where possible and readiness reports that tool as unavailable or requiring
   setup.

---

### User Story 4 - Reinstall or Update Safely (Priority: P2)

An operator can run the same installer again to repair or update the
workstation without duplicate application copies, managed runtime artifacts,
or Windows shortcuts, and without unnecessarily destroying valid operator
data or authentication.

**Why this priority**: Workstation maintenance must be safe and predictable
after the initial installation.

**Independent Test**: Run the installer twice on the same supported test
workstation and compare application location, runtime identity, shortcut,
configuration, and representative operator-owned data before and after.

**Acceptance Scenarios**:

1. **Given** a prior successful bootstrap, **When** the operator reruns the
   installer, **Then** it repairs or reuses the same approved application
   location and Feature 011 runtime without duplicates, and offers a newer
   verified release only after showing it and receiving confirmation.
2. **Given** valid operator configuration, NOC data, or authentication already
   exists, **When** bootstrap is rerun, **Then** it preserves those items
   unless the operator explicitly approves a replacement.

### Edge Cases

- WSL is absent, disabled, unsupported, or cannot start.
- The approved Ubuntu distribution is absent, inaccessible, or unsupported.
- Application acquisition is unavailable, incomplete, untrusted, or does not
  match the approved source identity.
- The target per-user installation location is unavailable, unsafe, or
  contains an incompatible existing application.
- A prior installation is interrupted while acquiring or replacing
  application-owned files.
- The installer lacks permission for a prerequisite change that requires
  elevation or explicit operator consent.
- The operator declines a consequential prerequisite or tool installation.
- An optional tool installation succeeds but its operator authentication,
  configuration, or service access remains incomplete.
- A readiness probe times out, returns malformed data, or emits sensitive
  output.
- The current Windows Desktop is redirected through OneDrive.
- A pre-existing shortcut, service, launcher, virtual environment, or
  application checkout is partially installed or stale.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The product MUST provide a Windows-launched installer package
  named **SESAMI-NOC-Operations-Setup.exe** for a fresh supported workstation.
- **FR-002**: The installer MUST work without a pre-existing NOC Web
  repository, Feature 011 runtime, Python virtual environment, systemd user
  service, launcher, or SESAMI NOC Operations shortcut.
- **FR-003**: The installer MUST detect WSL availability, the approved Ubuntu
  distribution, and supported runtime prerequisites before attempting
  application setup.
- **FR-004**: The installer MUST distinguish WSL missing, distribution missing,
  unsupported runtime, source-verification failure, permission/approval
  blocker, and application configuration failure with separate safe,
  actionable diagnostics.
- **FR-005**: The installer MUST obtain application source only from the
  approved signed GitHub release and verify its identity and completeness
  against the published SHA-256 manifest before executing it.
- **FR-006**: The installer MUST use one deterministic per-user WSL
  application location, reuse it on rerun, and reject unsafe or incompatible
  target paths.
- **FR-007**: The installer MUST invoke the existing Feature 011 installer for
  managed runtime configuration, service installation, health verification,
  localhost-only behavior, and Windows shortcut creation rather than
  duplicating those responsibilities.
- **FR-008**: The installer MUST create the NOC Web virtual environment from
  the application's pinned dependencies and verify it without requiring the
  operator to pre-activate an environment.
- **FR-009**: The installer MUST create exactly one **SESAMI NOC Operations**
  shortcut by reusing Feature 011, including its Windows known-folder and
  redirected-Desktop behavior.
- **FR-010**: The installer MUST package **SESAMI-NOC-Operations-Setup.exe**
  and its multi-resolution icon using only
  `assets/windows/sesami-noc-operations.png`; it MUST NOT substitute,
  redesign, or reinterpret the approved branding asset.
- **FR-011**: The installer MUST request explicit operator confirmation before
  any application replacement or optional tool installation that changes the
  workstation. It MUST guide, rather than initiate, WSL or Ubuntu platform
  setup.
- **FR-012**: The installer MUST stop before making a consequential change if
  the operator declines confirmation or required authorization is unavailable.
- **FR-013**: The installer MUST attempt approved installation or configuration
  of Atlas, GitHub Copilot CLI, Microsoft 365 CLI, Datadog MCP components, and
  noc-tools only when an approved distribution contract exists; otherwise it
  MUST report safe setup guidance without an unapproved substitute.
- **FR-014**: Atlas installation MUST preserve the Feature 011 trusted
  Linuxbrew deployment model. Atlas readiness MUST distinguish missing,
  authentication-required, unavailable, and ready states using the supported
  machine-readable authentication-status result.
- **FR-015**: The installer MUST report GitHub Copilot CLI, Microsoft 365 CLI,
  Datadog MCP, and noc-tools installation and readiness independently, using
  existing approved readiness behavior where applicable.
- **FR-016**: The installer MUST NOT embed, clone, migrate, read, distribute,
  or log credentials, sessions, tokens, cookies, secrets, or authentication
  files from another operator or workstation.
- **FR-017**: Installation and authentication MUST remain separate: bootstrap
  may install approved binaries and application-owned configuration, but
  operator-specific sign-in or credential configuration MUST be initiated and
  completed by the operator.
- **FR-018**: After bootstrap, the existing readiness UI MUST report each
  integration as READY, SETUP REQUIRED, or UNAVAILABLE with safe corrective
  guidance and without sensitive command output.
- **FR-019**: Rerunning the installer MUST be idempotent and MUST NOT create
  duplicate repositories, virtual environments, systemd services, Windows
  launchers, Desktop shortcuts, or runtime configuration. It MUST repair or
  reuse the installed verified release by default, and MUST show and obtain
  confirmation before replacing it with a newer verified release.
- **FR-020**: Rerunning the installer MUST preserve valid operator data,
  runtime configuration, and authentication unless the operator explicitly
  approves replacement of application-owned content.
- **FR-021**: The installer MUST fail closed if application acquisition or
  verification fails, and MUST not report partial setup as successful.
- **FR-022**: The installer MUST maintain the NOC Web read-only defaults,
  explicit confirmation for state-changing application actions, API/UI
  consistency, and advisory human-reviewed AI behavior.
- **FR-023**: Automated regression coverage MUST exercise acquisition
  validation, clean-workstation prerequisites, Feature 011 handoff,
  idempotent rerun, branded shortcut creation, dependency and
  authentication-state reporting, credential non-migration, and safe failure
  behavior.
- **FR-024**: Release acceptance MUST run on a clean supported Windows and WSL
  environment without a NOC Web checkout, Feature 011 runtime, or SESAMI NOC
  Operations shortcut, and demonstrate installer launch, application
  acquisition, runtime setup, shortcut launch, service reuse, dependency
  reporting, credential isolation, and safe rerun.
- **FR-025**: The installer MUST NOT inherit the operator's full interactive
  Windows or WSL PATH; it MUST use controlled, approved locations only.
- **FR-026**: The installer MUST use the approved noc-tools distribution and
  compatibility contract defined by the versioned NOC Web release manifest.

### Key Entities

- **Bootstrap Installation**: The application-owned installation record that
  identifies the approved application release, per-user target location,
  installation state, and safe last-result category.
- **Source Verification Record**: Non-secret evidence that acquired
  application content matches the approved release identity and is safe to
  execute.
- **Prerequisite Assessment**: A current, safe result for WSL, distribution,
  runtime support, permissions, and required operator approval.
- **Dependency Provisioning Result**: A separate non-secret installation,
  configuration, authentication-required, ready, or unavailable result for
  each optional operational integration.
- **Branding Asset**: The approved SESAMI image used unchanged to produce
  package and shortcut branding artifacts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a clean supported test workstation, an operator can complete
  core NOC Web bootstrap from launching the installer to a healthy branded
  shortcut in 20 minutes or less, excluding time spent on operator-controlled
  authentication.
- **SC-002**: In clean-workstation acceptance tests, 100% of successful
  bootstrap runs acquire verified application content, create one managed
  runtime, and create one branded shortcut without manual repository cloning,
  terminal startup, or environment activation.
- **SC-003**: In clean-workstation acceptance tests, the first shortcut launch
  opens NOC Web only after health succeeds and a second launch reuses the same
  managed service without an additional application process.
- **SC-004**: Across automated dependency-state cases, 100% of missing,
  authentication-required, unavailable, and ready dependency outcomes are
  separately identified without exposing a credential, token, session,
  cookie, secret, or raw command output.
- **SC-005**: Across rerun and interrupted-installation tests, 100% of
  preserved valid operator data, runtime configuration, authentication, and
  application identity remain unchanged unless the operator explicitly
  approves replacement.
- **SC-006**: In prerequisite and source-verification failure tests, 100% of
  failures stop before unverified application content executes and identify a
  safe corrective next step.
- **SC-007**: The package and resulting shortcut display the approved SESAMI
  NOC Operations branding at all supported Windows icon sizes without a
  substituted asset.

## Assumptions

- A supported workstation is Windows 10 or Windows 11 with an approved WSL2
  Ubuntu distribution and sufficient per-user storage.
- Feature 011 remains the sole owner of NOC Web's managed runtime, runtime
  configuration, hidden launcher, health check, localhost behavior, and
  desktop shortcut.
- The bootstrap installer owns application acquisition and handoff to Feature
  011, not NOC operational data or operator authentication.
- Optional integrations do not block core application bootstrap when their
  installation, configuration, or authentication is incomplete.
- The approved SESAMI branding asset is present in the release package and may
  be transformed only into required package icon sizes.
- Clean-workstation acceptance uses an isolated supported Windows and WSL
  environment, not a developer's existing operational data or credentials.
