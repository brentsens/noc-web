# UI Contract: Resource Navigation

This feature exposes a user-facing navigation contract and adds no HTTP API or external-system
integration. Exact destination names, groups, and URLs are defined in the feature specification
and represented by one shared catalog.

## Global Navigation

- Each application page with the global sidebar presents one internal Resources destination.
- The Resources destination preserves a valid selected-shift value when that context is present.
- Individual external destinations do not appear as separate sidebar items.

## Resources Directory

- The directory presents SES Environments, Tickets & Support, Documentation, and Observability.
- A normal page load visibly renders all four groups and all 11 destinations with the exact URLs
  specified in FR-003 through FR-006; catalog configuration without browser rendering is
  insufficient.
- DEMO SES is visibly distinguished from the three production SES environments.
- Each external destination has a visible external-navigation indicator such as ↗ and opens in a
  new tab isolated from the originating page (`target="_blank"` and
  `rel="noopener noreferrer"`).
- Groups are collapsible and expanded on initial desktop display. Operators can collapse and
  reopen each group; all destinations remain reachable at narrow widths without horizontal page
  scrolling.

## Dashboard Quick Links

- Dashboard exposes exactly four Quick Links: external NOC Jira, Salesforce, and Datadog, plus one
  internal link labeled “Resources →” to the complete directory.
- External Quick Links use the same destinations as the Resources directory; the URL inventory
  must not be copied into Dashboard markup.

## Context and Side Effects

- External links use their configured destination unchanged. No shift, ticket, investigation,
  Assistant, or other NOC Web context is added or sent.
- NOC Web does not probe, preload, fetch, or authenticate to a destination.
- Resource selection does not write or update operational records and does not change confirmation
  requirements in existing workflows.
