from backend.config import NOC_ROOT


REPORT_TYPES = {
    "shift-analysis": {
        "file": "ai-shift-analysis.md",
        "title": "Shift Analysis",
    },
    "shift-summary": {
        "file": "ai-shift-summary.md",
        "title": "Shift Summary",
    },
    "followups": {
        "file": "ai-followups.md",
        "title": "Follow-ups",
    },
    "handover-review": {
        "file": "ai-handover-review.md",
        "title": "Handover Review",
    },
}


def get_ai_reports(
    shift_date: str,
) -> list:

    reports_dir = (
        NOC_ROOT
        / shift_date
        / "reports"
    )

    reports = []


    if not reports_dir.is_dir():
        return reports


    for report_name, definition in (
        REPORT_TYPES.items()
    ):

        report_file = (
            reports_dir
            / definition["file"]
        )


        if not report_file.is_file():
            continue


        reports.append({
            "name":
                report_name,

            "title":
                definition["title"],

            "file":
                definition["file"],

            "available":
                True,
        })


    return reports


def get_ai_report(
    shift_date: str,
    report_name: str,
) -> dict | None:

    definition = REPORT_TYPES.get(
        report_name
    )


    if definition is None:
        return None


    report_file = (
        NOC_ROOT
        / shift_date
        / "reports"
        / definition["file"]
    )


    if not report_file.is_file():
        return None


    try:

        content = report_file.read_text(
            encoding="utf-8"
        ).strip()

    except (
        OSError,
        UnicodeError,
    ):

        return None


    return {
        "name":
            report_name,

        "title":
            definition["title"],

        "file":
            definition["file"],

        "content":
            content,

        "available":
            True,
    }