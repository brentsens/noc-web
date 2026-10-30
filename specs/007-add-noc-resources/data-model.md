# Data Model: NOC Resources Experience

The feature adds no persisted operational data. Its resource catalog is static presentation
configuration that is shipped with the frontend; selecting a destination does not create or change
NOC Web records.

## Resource Group

Represents one visible category on the Resources page.

| Attribute | Meaning | Constraint |
|---|---|---|
| Title | Display name of the category | One of SES Environments, Tickets & Support, Documentation, or Observability |
| Order | Position in the directory | Stable order matching the feature specification |
| Resources | Destinations belonging to the group | Contains the exact entries assigned by FR-003 through FR-006 |
| Disclosure state | Whether the group contents are expanded or collapsed | Transient operator-controlled presentation state; initially expanded and not persisted |

## Resource Shortcut

Represents one operator-controlled external destination.

| Attribute | Meaning | Constraint |
|---|---|---|
| Name | Operator-visible destination name | Unique within the catalog; matches the specified resource name |
| URL | Exact destination supplied by the feature specification | Immutable unless the approved resource inventory is deliberately updated; never decorated with NOC Web context |
| Environment | Optional SES environment classification | `production` for USPRI, EU, and MEXPRI; `demo` for DEMO; absent for other groups |
| Dashboard Quick Link | Whether Dashboard exposes this external destination | True only for NOC Jira, Salesforce, and Datadog |

Each shortcut belongs to exactly one Resource Group. Dashboard external Quick Links are references
to Resource Shortcuts, not separate destinations or a second URL inventory. The internal Resources
Dashboard link is a route to the directory, not an external Resource Shortcut.

## Lifecycle and State

- The catalog is read-only at runtime and is not operator-editable.
- Opening a shortcut starts browser navigation only after operator action.
- External destination availability, authentication, and authorization are managed by the
  destination, not stored or inferred by NOC Web.
- Resource groups are collapsible and expanded on initial display. Collapse state is temporary and
  is not persisted; responsive layout changes presentation without changing resource membership.
- A selected shift is internal navigation context only and is never part of a resource URL.
