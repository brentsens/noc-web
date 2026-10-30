from datetime import date

from fastapi import (
    APIRouter,
    HTTPException,
)
from pydantic import BaseModel, StrictBool

from backend.services.investigations import (
    get_investigation,
    get_investigations,
    reject_investigation,
    review_investigation,
)


router = APIRouter(
    prefix="/api/shifts",
    tags=["investigations"],
)

class ReviewInvestigationRequest(BaseModel):
    confirmed: StrictBool
    finding: str
    state: str
    reviewedBy: str | None = None


class _ConfirmedRequest(BaseModel):
    confirmed: StrictBool


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
    "/{shift_date}/investigations"
)
def investigations(
    shift_date: str,
):

    validate_shift_date(
        shift_date
    )


    results = get_investigations(
        shift_date
    )


    return {
        "shiftDate":
            shift_date,

        "count":
            len(results),

        "investigations":
            results,
    }


@router.get(
    "/{shift_date}/investigations/"
    "{investigation_name}"
)
def investigation(
    shift_date: str,
    investigation_name: str,
):

    validate_shift_date(
        shift_date
    )


    result = get_investigation(
        shift_date,
        investigation_name,
    )


    if result is None:

        raise HTTPException(
            status_code=404,
            detail=(
                "Investigation not found"
            ),
        )


    return result


@router.post(
    "/{shift_date}/investigations/"
    "{investigation_name}/review"
)
def review(
    shift_date: str,
    investigation_name: str,
    request: ReviewInvestigationRequest,
):
    validate_shift_date(shift_date)
    if request.confirmed is not True:
        raise HTTPException(
            status_code=422,
            detail="This operation requires confirmed: true.",
        )
    try:
        return review_investigation(
            shift_date,
            investigation_name,
            request.finding,
            request.state,
            request.reviewedBy,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found",
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        )


@router.post(
    "/{shift_date}/investigations/"
    "{investigation_name}/reject"
)
def reject(
    shift_date: str,
    investigation_name: str,
    request: _ConfirmedRequest,
):
    validate_shift_date(shift_date)
    if request.confirmed is not True:
        raise HTTPException(status_code=422, detail="This operation requires confirmed: true.")
    try:
        return reject_investigation(shift_date, investigation_name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Investigation not found")
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
