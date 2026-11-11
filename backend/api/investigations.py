from datetime import date
import re
from typing import Literal

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)
from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr

from backend.config import ConfigurationError
from backend.services.investigations import (
    InvestigationAttachmentError,
    attach_datadog_incident,
    get_investigation,
    get_investigations,
    reject_investigation,
    transition_investigation,
)
from backend.services.ai_provider import (
    PROVIDER_DEEPSEEK,
    PROVIDER_OLLAMA,
    resolve_provider_runtime_for,
)
from backend.services.investigation_ai import INVESTIGATION_SYSTEM_PROMPT
from backend.services.investigation_generation import (
    GenerationError,
    InvestigationValidationError,
    create_investigation,
    preview_investigation,
    retry_investigation_generation,
)


router = APIRouter(
    prefix="/api/shifts",
    tags=["investigations"],
)

class ReviewInvestigationRequest(BaseModel):
    confirmed: StrictBool
    lifecycleStatus: Literal["escalated_to_incident", "cured"]
    finding: StrictStr
    selectedShiftDate: StrictStr
    reviewedBy: StrictStr | None = None


class _ConfirmedRequest(BaseModel):
    confirmed: StrictBool


class AttachDatadogIncidentRequest(BaseModel):
    confirmed: StrictBool
    incidentId: StrictStr
    selectedShiftDate: StrictStr


class PreviewInvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incidentId: StrictStr
    displayTitle: StrictStr | None = None
    name: StrictStr | None = None
    notebookUrl: StrictStr
    provider: StrictStr | None = None


class CreateInvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    previewId: StrictStr
    name: StrictStr
    notebookUrl: StrictStr
    confirmed: StrictBool
    provider: StrictStr | None = None


class LocalRetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retryToken: StrictStr
    confirmed: StrictBool


def validate_shift_date(
    shift_date: str,
) -> None:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", shift_date):
        raise HTTPException(
            status_code=400,
            detail="shift_date must use YYYY-MM-DD format",
        )
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
    if error.retry_metadata:
        detail["localRetry"] = error.retry_metadata
    return detail


def _requested_runtime(provider: str | None):
    if provider is None:
        return None
    if provider not in {PROVIDER_DEEPSEEK, PROVIDER_OLLAMA}:
        raise HTTPException(
            status_code=422,
            detail="provider must be deepseek-api or ollama.",
        )
    return resolve_provider_runtime_for(
        provider,
        system_prompt=INVESTIGATION_SYSTEM_PROMPT,
    )


@router.post("/{shift_date}/investigations/preview")
def preview(
    shift_date: str,
    request: PreviewInvestigationRequest,
):
    _validate_generation_shift(shift_date)
    try:
        return preview_investigation(
            shift_date,
            request.name,
            request.notebookUrl,
            request.incidentId,
            display_title=request.displayTitle,
            provider_runtime=_requested_runtime(request.provider),
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
    try:
        result = create_investigation(
            shift_date,
            request.name,
            request.notebookUrl,
            request.previewId,
            request.confirmed,
            provider_runtime=_requested_runtime(request.provider),
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


@router.post("/{shift_date}/investigations/local-retry", status_code=201)
def retry_local(
    shift_date: str,
    request: LocalRetryRequest,
):
    _validate_generation_shift(shift_date)
    if request.confirmed is not True:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "retry-confirmation-required",
                "message": "Explicit confirmation is required for local retry.",
            },
        )
    try:
        result = retry_investigation_generation(
            shift_date,
            request.retryToken,
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
    view: Literal["active", "history"] = Query("active"),
):

    validate_shift_date(
        shift_date
    )


    results = get_investigations(
        shift_date,
        view,
    )


    return {
        "shiftDate":
            shift_date,

        "selectedShiftDate":
            shift_date,

        "view":
            view,

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
    selectedShiftDate: str | None = Query(None),
):

    validate_shift_date(
        shift_date
    )
    if selectedShiftDate is not None:
        validate_shift_date(selectedShiftDate)


    result = get_investigation(
        shift_date,
        investigation_name,
        selectedShiftDate,
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
        return transition_investigation(
            shift_date,
            investigation_name,
            request.selectedShiftDate,
            request.lifecycleStatus,
            request.finding,
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
    except OSError:
        raise HTTPException(
            status_code=500,
            detail="Investigation lifecycle could not be stored.",
        ) from None


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


@router.post(
    "/{shift_date}/investigations/"
    "{investigation_name}/datadog-incident"
)
def attach_incident(
    shift_date: str,
    investigation_name: str,
    request: AttachDatadogIncidentRequest,
):
    validate_shift_date(shift_date)
    if request.confirmed is not True:
        raise HTTPException(
            status_code=422,
            detail="This operation requires confirmed: true.",
        )
    try:
        return attach_datadog_incident(
            shift_date,
            investigation_name,
            request.selectedShiftDate,
            request.incidentId,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Investigation not found")
    except InvestigationAttachmentError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=str(error),
        ) from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except OSError:
        raise HTTPException(
            status_code=500,
            detail="Datadog incident attachment could not be stored.",
        ) from None
