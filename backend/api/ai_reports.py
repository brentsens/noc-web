from datetime import date

from fastapi import (
    APIRouter,
    HTTPException,
)

from backend.services.ai_reports import (
    get_ai_report,
    get_ai_reports,
)


router = APIRouter(
    prefix="/api/shifts",
    tags=["ai-reports"],
)


def validate_shift_date(
    shift_date: str,
) -> None:

    try:

        date.fromisoformat(
            shift_date
        )

    except ValueError:

        raise HTTPException(
            status_code=400,
            detail=(
                "shift_date must use "
                "YYYY-MM-DD format"
            ),
        )


@router.get(
    "/{shift_date}/ai-reports"
)
def ai_reports(
    shift_date: str,
):

    validate_shift_date(
        shift_date
    )


    reports = get_ai_reports(
        shift_date
    )


    return {
        "shiftDate":
            shift_date,

        "count":
            len(reports),

        "reports":
            reports,
    }


@router.get(
    "/{shift_date}/ai-reports/"
    "{report_name}"
)
def ai_report(
    shift_date: str,
    report_name: str,
):

    validate_shift_date(
        shift_date
    )


    report = get_ai_report(
        shift_date,
        report_name,
    )


    if report is None:

        raise HTTPException(
            status_code=404,
            detail="AI report not found",
        )


    return report