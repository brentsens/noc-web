# Data Model: Confirmation-Gated Datadog Investigation Creation

**Feature**: [spec.md](spec.md)
**Design**: [plan.md](plan.md)

This feature uses the existing shift-scoped local investigation store and review state. It does not create Jira, Datadog, Shift Notes, or handover records.

## Investigation Request

Transient validated input for preview and confirmed creation.

| Field | Type | Rules |
|---|---|---|
| `shiftDate` | ISO date string | Comes from the validated shift-scoped route/context; never silently substituted |
| `name` | String | Required; trimmed and normalized as below |
| `normalizedName` | String | Lowercase ASCII kebab-case; 1–80 chars; starts with letter/digit; whitespace and repeated hyphens collapse |
| `notebookUrl` | String | Exact submitted value; HTTPS URL matching the approved Datadog Notebook pattern only |
| `confirmed` | Boolean | Required and true for creation; absent/false never invokes the generator |

The preview form does not persist this entity. Preview responses expose a logical shift/name destination, never an absolute workstation path.

## Generated Investigation

Durable record at `{NOC_ROOT}/{YYYY-MM-DD}/investigations/{name}/investigation.md`, produced by `noc-inv` and validated before publication or controlled review.

| Field | Type | Rules |
|---|---|---|
| `shiftDate` | ISO date string | Must equal the requested shift |
| `name` | String | Must equal the normalized request identifier |
| `notebookUrl` | String | Exact validated FINAL Notebook URL is preserved in metadata |
| `provenance` | String | Must identify `noc-inv` or Copilot MCP evidence provenance |
| `generationStatus` | Enum | `completed`, `failed`, `timed_out`, or `unavailable` |
| `validationStatus` | Enum | `ready_for_review` or `needs_review` |
| `reviewState` | Enum | Uses existing projection values: `unreviewed`, `reviewed`, `rejected`, or `unavailable`; new records start `unreviewed` |
| `content` | Structured Markdown sections | Summary, Confirmed Findings, Current Status, Next Actions when required, and Handover Summary |
| `createdAt` | Timestamp | Local record creation time, using the existing record format |

The current Markdown record uses a title and `- Key: Value` metadata lines, including `Status`, `Source of truth`, and `Datadog Notebook`. The creation path must preserve compatible metadata and add the shift, normalized investigation identifier, evidence provenance, generation state, and validation state as needed. Existing review decisions remain in `reviewed-context.json` (`finding`, `state`, `reviewedAt`, `reviewedBy`); new records must not create reviewed context.

### Output validation

- Required metadata must match the request and configured shift.
- Provenance must match the approved noc-inv/Copilot MCP source.
- Required headings must exist; required text sections cannot contain only empty/placeholder values.
- Unsafe or malformed structure is not published as a normal valid record.
- Safe incomplete output may be retained as `needs_review` for controlled inspection.
- Raw Notebook content, raw evidence, temporary Copilot context, provider diagnostics, credentials, and tokens are never handover fields.
- The existing concise reviewed finding remains the only finding eligible for propagation.

## Generation Readiness

Read-only capability view based on Feature 005's configuration profile.

| Capability | Meaning |
|---|---|
| `nocInvAvailable` | Configured `noc-inv` executable is present and usable |
| `copilotCliAvailable` | Configured GitHub Copilot CLI is present and usable |
| `storageAvailable` | Configured local investigation storage is writable |
| `available` | Required capabilities are all available |

Readiness performs no investigation execution, Notebook fetch, authentication, or data mutation. It must not expose raw process output or local filesystem paths. Datadog MCP/authentication failure is reported as a controlled generation failure, not by direct probing.

## State Transitions

```text
Preview: submitted -> validated preview | validation error

Confirmed creation:
  confirmed request -> conflict | unavailable | timed_out | failed
  confirmed request -> generated -> ready_for_review + unreviewed
  confirmed request -> generated/incomplete -> needs_review + unreviewed

Operator action:
  unreviewed -> reviewed
  unreviewed -> rejected
```

Only `validationStatus=ready_for_review` plus `lifecycle.reviewState=reviewed` may supply concise findings to existing downstream projections. Rejected, unreviewed, malformed, or unavailable records remain excluded.
