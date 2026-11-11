import subprocess

from datetime import date

from fastapi import (
    APIRouter,
    HTTPException,
)
from pydantic import BaseModel, StrictBool, StrictStr

from backend.services.ai_provider import (
    PROVIDER_DEEPSEEK,
    PROVIDER_OLLAMA,
    resolve_provider_runtime_for,
)
from backend.services.handover import (
    HandoverGenerationError,
    generate_handover,
    get_handover,
    preview_handover,
    regenerate_handover,
    retry_handover_generation,
)
from backend.services.handover_ai import HANDOVER_SYSTEM_PROMPT

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
    provider: StrictStr | None = None


class LocalRetryRequest(BaseModel):
    confirmed: StrictBool
    retryToken: StrictStr


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
        system_prompt=HANDOVER_SYSTEM_PROMPT,
    )


def _generation_detail(error: HandoverGenerationError) -> dict:
    detail = {"code": error.code, "message": error.message}
    if error.retry_metadata:
        detail["localRetry"] = error.retry_metadata
    return detail


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
            detail=_generation_detail(error),
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
            provider_runtime=_requested_runtime(request.provider),
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
            detail=_generation_detail(error),
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
            provider_runtime=_requested_runtime(request.provider),
        )

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except HandoverGenerationError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=_generation_detail(error),
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

@router.post("/{shift_date}/handover/local-retry")
def retry_local_handover(
    shift_date: str,
    request: LocalRetryRequest,
):
    if request.confirmed is not True:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "retry-confirmation-required",
                "message": "Explicit confirmation is required for local retry.",
            },
        )
    try:
        date.fromisoformat(shift_date)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="shift_date must use YYYY-MM-DD format",
        ) from None
    try:
        return retry_handover_generation(
            shift_date,
            request.retryToken,
        )
    except FileExistsError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except HandoverGenerationError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=_generation_detail(error),
        ) from None
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Handover local retry timed out.",
        ) from None
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error)) from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
