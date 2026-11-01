import subprocess

from datetime import date

from fastapi import (
    APIRouter,
    HTTPException,
)

from pydantic import BaseModel

from backend.services.dependencies import (
    DependencyUnavailable,
    ExternalOperationFailed,
)
from backend.services.handover_delivery import (
    preview_handover_email,
    send_handover_email,
)


router = APIRouter(
    prefix="/api/shifts",
    tags=["handover-delivery"],
)


class HandoverPreviewRequest(
    BaseModel
):
    recipient: str | None = None

class HandoverSendRequest(
    BaseModel
):
    recipient: str | None = None
    confirmed: bool = False

@router.post(
    "/{shift_date}/handover/send"
)
def send_delivery(
    shift_date: str,
    request: HandoverSendRequest,
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

    if request.confirmed is not True:
        raise HTTPException(
            status_code=409,
            detail=(
                "Explicit confirmation is "
                "required before sending."
            ),
        )

    try:
        return send_handover_email(
            shift_date,
            request.recipient,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except DependencyUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail={"code": error.code, "message": error.message},
        ) from None

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="M365 email send timed out.",
        )

    except ExternalOperationFailed as error:
        raise HTTPException(
            status_code=503,
            detail={"code": error.code, "message": error.message},
        ) from None

    except RuntimeError:
        raise HTTPException(
            status_code=502,
            detail="Microsoft 365 email send failed.",
        ) from None


@router.post(
    "/{shift_date}/handover/preview"
)
def preview_delivery(
    shift_date: str,
    request: HandoverPreviewRequest,
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

    try:
        return preview_handover_email(
            shift_date,
            request.recipient,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except DependencyUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail={"code": error.code, "message": error.message},
        ) from None

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="M365 email preview timed out.",
        )

    except ExternalOperationFailed as error:
        raise HTTPException(
            status_code=503,
            detail={"code": error.code, "message": error.message},
        ) from None

    except RuntimeError:
        raise HTTPException(
            status_code=502,
            detail="Microsoft 365 email preview failed.",
        ) from None