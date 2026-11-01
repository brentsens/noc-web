# Feature Specification: Trusted Release Pipeline

**Feature Branch**: `013-trusted-release-pipeline`

**Created**: 2026-11-01

**Status**: Draft

**Input**: User description: "Create an automated trusted release pipeline for
noc-web that publishes immutable, verifiable release artifacts required by the
fresh-workstation bootstrap."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Publish a Verified Versioned Release (Priority: P1)

A release manager creates an explicit version tag and receives a published NOC
Web release only after the complete validation suite succeeds. The published
release is tied to that exact tag and provides the stable archive and checksum
names required by a fresh-workstation installer.

**Why this priority**: Feature 012 cannot safely acquire NOC Web until an
immutable, validated release contract exists.

**Independent Test**: Create a valid version tag on a test commit and confirm
one release publishes `noc-web-vX.Y.Z.tar.gz` and
`noc-web-vX.Y.Z.sha256`, both associated with that exact tag.

**Acceptance Scenarios**:

1. **Given** an explicit valid version tag, **When** release validation
   succeeds, **Then** exactly one release archive and its matching checksum
   are published using the tag-derived naming contract.
2. **Given** a tag that does not match the supported version format, **When**
   it is created, **Then** no release is published.
3. **Given** validation fails, **When** a valid version tag is processed,
   **Then** no archive, checksum, or release publication occurs.

---

### User Story 2 - Verify Release Provenance (Priority: P1)

A workstation bootstrap consumer can determine that a downloaded release
archive is the exact artifact produced for the published tag and has not been
substituted or altered.

**Why this priority**: The bootstrap must fail closed instead of executing an
unverified download.

**Independent Test**: Retrieve a published test release and confirm its
archive checksum and provenance information identify the same tagged source;
substituting or altering either artifact fails verification.

**Acceptance Scenarios**:

1. **Given** a published release, **When** its archive is retrieved with its
   checksum and provenance information, **Then** all identify the exact tagged
   source and artifact.
2. **Given** an altered archive, checksum, or provenance reference, **When**
   verification is attempted, **Then** verification fails before the archive
   can be used.
3. **Given** a release attempt, **When** trust evidence cannot be generated,
   **Then** publication fails and no success result is reported.

---

### User Story 3 - Receive a Safe Bootstrap Archive (Priority: P1)

A fresh-workstation installer receives a complete NOC Web application archive
that contains only the release-required content and no workstation state,
operator data, credentials, development environments, or temporary content.

**Why this priority**: A release archive must be portable and safe to
distribute to a new operator.

**Independent Test**: Inspect a published test archive and confirm it contains
the required bootstrap/runtime inputs while excluding the documented unsafe and
development-only content classes.

**Acceptance Scenarios**:

1. **Given** a successfully published release, **When** its archive is
   inspected, **Then** it contains the release-required application content
   and excludes repository metadata, virtual environments, caches, local
   runtime configuration, credentials, tokens, logs, operator data, and
   temporary files.
2. **Given** excluded local content exists in the source workspace, **When** a
   release is assembled, **Then** that content is absent from the archive.
3. **Given** required bootstrap/runtime content is absent from the candidate
   archive, **When** release validation runs, **Then** publication stops.

---

### User Story 4 - Validate the First Production Release (Priority: P2)

A release manager verifies the first real release against the documented
contract before Feature 012 relies on it for fresh-workstation bootstrap.

**Why this priority**: Automated checks reduce risk, but first-release
verification confirms the externally published contract works end to end.

**Independent Test**: Independently retrieve the first published release and
verify its tag association, archive name, checksum, provenance, safe contents,
and bootstrap-consumer compatibility before enabling Feature 012 release use.

**Acceptance Scenarios**:

1. **Given** the first real release is published, **When** the release manager
   verifies its documented contract, **Then** Feature 012 is enabled only if
   every required artifact and trust check succeeds.
2. **Given** any first-release verification check fails, **When** the result
   is recorded, **Then** Feature 012 remains blocked and the failure is
   actionable.

### Edge Cases

- A tag points to a commit that does not contain the expected release content.
- A release with the same tag or artifact name already exists.
- The archive is empty, malformed, or includes path traversal entries.
- Validation, checksum generation, provenance generation, or publication is
  interrupted.
- A release candidate contains a secret-like file, local operator data, or
  mutable development artifact.
- A consumer receives a checksum or provenance record for a different tag or
  archive.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The release process MUST publish releases only for explicit tags
  matching `vX.Y.Z`, where X, Y, and Z are decimal version components.
- **FR-002**: The release process MUST associate every published artifact with
  the exact commit identified by its triggering tag.
- **FR-003**: The release process MUST complete all required validation before
  creating or publishing any release artifact.
- **FR-004**: The release process MUST fail closed: a validation, packaging,
  checksum, provenance, or publication failure MUST prevent a successful
  release result.
- **FR-005**: The release process MUST publish exactly these stable,
  tag-derived artifact names: `noc-web-vX.Y.Z.tar.gz` and
  `noc-web-vX.Y.Z.sha256`.
- **FR-006**: The published checksum MUST represent the exact published
  archive and state the archive filename it verifies.
- **FR-007**: The release process MUST publish provenance information that
  identifies the exact published archive and the exact tagged source.
- **FR-008**: The release process MUST not store or require a long-lived
  private signing key in the repository or release archive.
- **FR-009**: The release archive MUST exclude repository metadata, virtual
  environments, caches, local runtime configuration, credentials, tokens,
  logs, operator data, temporary files, and other development-only local
  content.
- **FR-010**: The release process MUST reject an archive that contains unsafe
  paths or omits content required for the fresh-workstation bootstrap and
  managed runtime handoff.
- **FR-011**: The release process MUST never include credentials, tokens,
  cookies, sessions, private keys, or signing secrets in a published artifact,
  checksum, provenance record, or release notes.
- **FR-012**: The release contract MUST provide immutable source identity,
  archive, checksum, and provenance information that Feature 012 can retrieve
  and verify before executing release content.
- **FR-013**: The release process MUST have automated regression coverage for
  tag eligibility, archive naming, exclusion rules, required-content checks,
  checksum correctness, provenance publication, and failure-before-publish
  behavior where practical.
- **FR-014**: The first real release under this contract MUST be independently
  verified against the archive, checksum, provenance, tagged-commit, and
  safe-content requirements before Feature 012 consumes it.

### Key Entities

- **Release Candidate**: The exact tagged source selected for validation and
  packaging.
- **Release Archive**: The versioned portable application content distributed
  to fresh workstations.
- **Checksum Record**: The named integrity record for one release archive.
- **Provenance Record**: The independently verifiable evidence connecting one
  published archive to one tagged source.
- **First-Release Verification Record**: The non-secret approval or failure
  result that controls whether Feature 012 may use the new release contract.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of accepted valid-version test tags publish exactly one
  archive and one matching checksum with the documented tag-derived names.
- **SC-002**: 100% of simulated validation, packaging, checksum, provenance,
  or publication failures leave no successful release result.
- **SC-003**: 100% of inspected test archives exclude each documented
  unsafe/development content class and include all required bootstrap/runtime
  content.
- **SC-004**: 100% of altered archive, checksum, or provenance test cases
  fail consumer verification before application content is used.
- **SC-005**: The first real release is independently verified and recorded
  against all release-contract requirements before Feature 012 resumes.

## Assumptions

- A release manager controls creation of version tags in `brentsens/noc-web`.
- Existing repository tests are the required application validation baseline;
  release-specific regression checks will be added for this feature.
- Release provenance supplied by the publishing platform is the approved trust
  evidence, avoiding a long-lived private signing key.
- The release archive is source content for the existing Feature 011 runtime
  installer and Feature 012 bootstrap; it does not contain operator identity
  or operational data.
