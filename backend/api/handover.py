import subprocess

from datetime import date

from fastapi import (
    APIRouter,
    HTTPException,
)
from pydantic import BaseModel, StrictBool, StrictStr

from backend.services.handover import (
    HandoverGenerationError,
    generate_handover,
    get_handover,
    preview_handover,
    regenerate_handover,
)

from backend.services.end_shift import (
    get_end_shift_preflight,
)


router = APIRouter(
    prefix="/api/shifts",
    tags=["handover"],
)

class HandoverActionRequest(BaseModel):
    confirmed: StrictBool
    previewDigest: StrictStr | None = None


@router.get("/{shift_date}/handover")
def handover(
    shift_date: str,
):

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


    return get_handover(
        shift_date
    )

@router.post("/{shift_date}/handover/generation-preview")
def preview_generation(shift_date: str):
    try:
        date.fromisoformat(shift_date)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="shift_date must use YYYY-MM-DD format",
        )
    try:
        return preview_handover(shift_date)
    except HandoverGenerationError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code, "message": error.message},
        ) from None


@router.post("/{shift_date}/handover")
def create_handover(
    shift_date: str,
    request: HandoverActionRequest,
):
    if request.confirmed is not True:
        raise HTTPException(status_code=422, detail="This operation requires confirmed: true.")
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

    preflight = get_end_shift_preflight(
        shift_date
    )

    if not preflight["generation"]["enabled"]:
        raise HTTPException(
            status_code=409,
            detail=(
                preflight["generation"]["message"]
            ),
        )

    try:
        return generate_handover(
            shift_date,
            preview_digest=request.previewDigest,
        )

    except FileExistsError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        )

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except HandoverGenerationError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code, "message": error.message},
        ) from None

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail=(
                "Handover generation timed out."
            ),
        )

    except RuntimeError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        )

@router.post(
    "/{shift_date}/handover/regenerate"
)
def regenerate_existing_handover(
    shift_date: str,
    request: HandoverActionRequest,
):
    if request.confirmed is not True:
        raise HTTPException(status_code=422, detail="This operation requires confirmed: true.")
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

    preflight = get_end_shift_preflight(
        shift_date
    )

    if not preflight["ready"]:
        raise HTTPException(
            status_code=409,
            detail=(
                "End Shift preflight is not ready."
            ),
        )

    if not preflight["jiraSync"]["synced"]:
        raise HTTPException(
            status_code=409,
            detail=(
                "A successful Jira sync is required "
                "before regenerating the handover."
            ),
        )

    if not preflight["handover"]["exists"]:
        raise HTTPException(
            status_code=409,
            detail=(
                "No existing handover is available "
                "to regenerate."
            ),
        )

    try:
        return regenerate_handover(
            shift_date,
            preview_digest=request.previewDigest,
        )

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except HandoverGenerationError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code, "message": error.message},
        ) from None

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail=(
                "Handover regeneration timed out. "
                "The previous handover was restored."
            ),
        )

    except RuntimeError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        )