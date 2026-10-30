# Quickstart: Validate NOC Resources

## Prerequisites

- Work from the repository root with its existing `.venv` and frontend validation tools available.
- For browser validation, the application dependencies, including Uvicorn, are installed in `.venv`.
- Use only local automated checks; tests must not contact the configured external destinations.
- Use a modern browser for the real-page checks below. Synthetic DOM and module tests are
  supplemental and do not replace this browser validation.

## Automated Validation

Run focused frontend regression coverage:

```bash
./.venv/bin/python -m pytest tests/test_frontend_modules.py
```

Run the full regression suite:

```bash
./.venv/bin/python -m pytest tests
```

Check the shared resource module's ES-module syntax:

```bash
node --check --input-type=module < frontend/js/resources.js
```

Expected results:

- The catalog has all 11 exact destinations in the four required groups.
- The Resources page visibly renders all four groups and 11 links in the browser.
- Dashboard Quick Links contain exactly NOC Jira, Salesforce, Datadog, and the internal
  “Resources →” link.
- Every generated external link has a visible external indicator and safe new-tab attributes.
- No external link receives a selected shift or other NOC Web context.
- DEMO SES is identified as non-production; groups start expanded and can be collapsed/reopened.
- Every resource remains reachable at narrow widths without horizontal page scrolling.
- Module and frontend regression checks pass.

## Browser Smoke Check

Start the application locally:

```bash
./.venv/bin/python -m uvicorn backend.app:app --reload
```

Then open the Dashboard in a modern browser. This check is required even if the automated
configuration and synthetic DOM tests pass.

1. Confirm Dashboard shows exactly NOC Jira, Salesforce, Datadog, and the internal “Resources →”
   link.
2. Open Resources with a valid selected shift in the URL. Confirm the internal page retains that
   shift.
3. Confirm the page visibly renders all four groups and all 11 links. Verify every group is
   initially expanded, collapse and reopen a group, and confirm the contents remain available.
4. Inspect the 11 link destinations and safe new-tab attributes, including the DEMO distinction.
   Do not activate external links or probe external sites.
5. At a narrow browser width (320 CSS pixels), confirm all groups and destinations remain usable
   and the page has no horizontal scrolling.
6. Confirm the external resource URLs remain exact and have no shift or other NOC Web context.

## Expected Outcome

Operators can reach the three frequent destinations directly from Dashboard and all other
destinations through Resources. No external site is contacted unless an operator explicitly
activates its link, and no NOC Web context is attached to external navigation.
