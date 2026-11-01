# Data Model: Trusted Release Pipeline

## Release Candidate

| Field | Validation |
|---|---|
| `tag` | Matches `vX.Y.Z`; immutable explicit version tag. |
| `commit` | Exact tag target; matches the checked-out release source. |
| `state` | `validated`, `assembled`, `attested`, `published`, or safe failure. |

Transitions are strictly forward. A failure ends the candidate without a
published release.

## Release Archive

| Field | Validation |
|---|---|
| `filename` | Exactly `noc-web-vX.Y.Z.tar.gz`. |
| `tag` | Matches the candidate tag. |
| `entries` | Allowlisted relative paths only; no traversal or excluded content. |
| `sha256` | Matches the checksum record and provenance subject. |

## Checksum Record

| Field | Validation |
|---|---|
| `filename` | Exactly `noc-web-vX.Y.Z.sha256`. |
| `archiveFilename` | Matches the published archive name. |
| `sha256` | 64 lowercase hexadecimal characters matching the archive. |

## Provenance Record

| Field | Validation |
|---|---|
| `subject` | The final published archive digest. |
| `repository` | `brentsens/noc-web`. |
| `workflowIdentity` | The approved release workflow identity. |
| `commit` | Matches the candidate tag target. |

## First-Release Verification Record

| Field | Validation |
|---|---|
| `tag` | First tag published by this contract. |
| `checks` | Archive name, contents, checksum, provenance, tag target, and consumer verification all pass. |
| `status` | `approved` or a safe actionable failure. |

