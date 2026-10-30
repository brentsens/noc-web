# Research: NOC Resources Experience

**Date**: 2026-10-30

No unresolved technology or product decisions remain after clarification. The feature extends the
existing static frontend and uses established repository patterns; no external research or new
dependency is required.

## Decisions

### Keep the feature frontend-only

- **Decision**: Implement resource navigation in the existing static frontend; add no server route,
  external API client, persistence, or integration.
- **Rationale**: The specification defines Resources as operator-controlled shortcuts and explicitly
  prohibits probing, authentication, preloading, and direct service integrations.
- **Alternatives considered**: Fetching resource metadata from external systems or proxying
  destinations through the backend. Both would expand the security and availability boundary and
  violate the stated scope.

### Maintain one catalog and derive Dashboard shortcuts from it

- **Decision**: Keep the exact resource names, groups, URLs, environment labels, and Dashboard
  Quick Link membership in the shared resource catalog. The Resources page and Dashboard consume
  the catalog rather than copying external URLs.
- **Rationale**: One inventory prevents destination drift and preserves the exact supplied URLs.
  Marking only NOC Jira, Salesforce, and Datadog as Dashboard shortcuts makes the Quick Link limit
  explicit without a second URL list.
- **Alternatives considered**: Duplicating the three URLs in Dashboard markup or maintaining a
  separate Dashboard URL list. Both duplicate configuration and risk inconsistent destinations.

### Preserve shift context only for internal navigation

- **Decision**: Reuse the shared workflow-context behavior to preserve a valid selected shift on
  internal navigation to Resources; leave configured external URLs unchanged.
- **Rationale**: This matches the global navigation contract and prevents operational context from
  being passed to third parties.
- **Alternatives considered**: Appending shift parameters to every navigation link or treating
  external links as workflow links. Both would leak NOC Web context externally.

### Use native, collapsible resource groups

- **Decision**: Represent each resource group with a browser-native disclosure section. All groups
  start expanded, and operators can collapse or reopen them. Do not persist the collapsed state or
  automatically collapse groups based on viewport width.
- **Rationale**: The specification requires collapsible groups and desktop-first visibility.
  Native disclosure behavior supplies the interaction without custom state management, persistence,
  or a new dependency. Starting expanded on all viewport sizes preserves immediate access while
  allowing operators to reduce vertical content when needed.
- **Alternatives considered**: Custom JavaScript accordion state and automatic narrow-screen
  collapse. Both add complexity or hide content without a demonstrated need.

### Verify rendered behavior in a real browser

- **Decision**: Use focused pytest/Node checks for exact inventory, DOM rendering, safe link
  attributes, Dashboard membership, context isolation, and module syntax. Also require a local
  real-browser smoke check at desktop and narrow widths, including group toggle behavior.
- **Rationale**: The acceptance criteria require the full interface to render in a browser; catalog
  validation or a synthetic DOM alone is insufficient. A local browser check verifies the actual
  page without visiting external destinations.
- **Alternatives considered**: Relying only on module parsing or synthetic DOM tests. These do not
  establish that the real page renders and remains usable at narrow widths. Live external-site
  checks or automatic link probes are excluded because they violate the no-probe requirement.
