from datetime import date

from fastapi import (
    APIRouter,
    HTTPException,
)
from pydantic import BaseModel, StrictBool, StrictStr

from backend.config import ConfigurationError
from backend.services.investigations import (
    get_investigation,
    get_investigations,
    reject_investigation,
    review_investigation,
)
from backend.services.investigation_generation import (
    GenerationError,
    InvestigationValidationError,
    create_investigation,
    preview_investigation,
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


class PreviewInvestigationRequest(BaseModel):
    name: StrictStr | None = None
    notebookUrl: StrictStr | None = None


class CreateInvestigationRequest(PreviewInvestigationRequest):
    confirmed: StrictBool


def validate_shift_date(
    shift_date: str,
) -> None:
    try:
        date.fromisoformat(shift_date)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="shift_date must use YYYY-MM-DD format",
        )

def _validate_generation_shift(shift_date: str) -> None:
    try:
        validate_shift_date(shift_date)
    except HTTPException as error:
        raise HTTPException(
            status_code=422,
            detail={
                "field": "shiftDate",
                "code": "invalid_shift",
                "message": "Selected Shift must use YYYY-MM-DD format.",
            },
        ) from None


def _generation_error_detail(error: GenerationError) -> dict:
    detail = {
        "code": error.code,
        "message": error.message,
    }
    if error.field:
        detail["field"] = error.field
    return detail


@router.post("/{shift_date}/investigations/preview")
def preview(
    shift_date: str,
    request: PreviewInvestigationRequest,
):
    _validate_generation_shift(shift_date)
    try:
        return preview_investigation(
            shift_date, request.name, request.notebookUrl
        )
    except GenerationError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=_generation_error_detail(error),
        ) from None
    except InvestigationValidationError as error:
        raise HTTPException(
            status_code=422,
            detail={
                "field": error.field,
                "code": error.code,
                "message": error.message,
            },
        ) from None
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="Investigation request is invalid.",
        ) from None
    except ConfigurationError:
        raise HTTPException(
            status_code=503,
            detail="Investigation generation is unavailable.",
        ) from None


@router.post("/{shift_date}/investigations", status_code=201)
def create(
    shift_date: str,
    request: CreateInvestigationRequest,
):
    _validate_generation_shift(shift_date)
    if request.confirmed is not True:
        raise HTTPException(
            status_code=422,
            detail="This operation requires confirmed: true.",
        )
    try:
        result = create_investigation(
            shift_date, request.name, request.notebookUrl
        )
        return result.record
    except GenerationError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=_generation_error_detail(error),
        ) from None
    except InvestigationValidationError as error:
        raise HTTPException(
            status_code=422,
            detail={
                "field": error.field,
                "code": error.code,
                "message": error.message,
            },
        ) from None
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="Investigation request is invalid.",
        ) from None
    except ConfigurationError:
        raise HTTPException(
            status_code=503,
            detail="Investigation generation is unavailable.",
        ) from None


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
