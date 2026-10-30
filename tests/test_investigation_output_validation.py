from backend.services.investigation_generation import (
    InvestigationRequest,
    _validate_generated_record,
)


NOTEBOOK_URL = "https://app.datadoghq.com/notebook/123456/example-notebook"
REQUEST = InvestigationRequest(
    shift_date="2099-12-31",
    display_title="Checkout Latency",
    name="checkout-latency",
    notebook_url=NOTEBOOK_URL,
)


def _record(
    *,
    shift="2099-12-31",
    name="checkout-latency",
    notebook=NOTEBOOK_URL,
    provenance="noc-inv",
    summary="Latency increased after deployment.",
):
    return (
        "# Investigation: Checkout Latency\n"
        f"- Investigation Name: {name}\n"
        "- Display Title: Checkout Latency\n"
        f"- Shift Date: {shift}\n"
        f"- FINAL Datadog Notebook: {notebook}\n"
        f"- Evidence Provenance: {provenance}\n"
        f"\n## Summary\n{summary}\n"
        "\n## Confirmed Findings\nQueue depth is elevated.\n"
        "\n## Current Status\nService remains available.\n"
        "\n## Next Actions\nMonitor queue depth.\n"
        "\n## Handover Summary\nContinue monitoring queue depth.\n"
    )


def test_complete_generated_record_is_ready_for_review():
    provenance, errors = _validate_generated_record(_record(), REQUEST)

    assert provenance == "noc-inv"
    assert errors == []


def test_record_with_wrong_shift_name_url_or_provenance_needs_review():
    provenance, errors = _validate_generated_record(
        _record(
            shift="2099-12-30",
            name="other-investigation",
            notebook="https://app.datadoghq.com/notebook/123456/other",
            provenance="manual",
        ),
        REQUEST,
    )

    assert provenance == ""
    assert {"shift", "name", "notebook", "provenance"} <= set(errors)


def test_placeholder_only_required_sections_need_review():
    _, errors = _validate_generated_record(_record(summary="TBD"), REQUEST)

    assert "section:Summary" in errors
