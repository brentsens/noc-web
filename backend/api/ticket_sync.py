import subprocess

from fastapi import (
    APIRouter,
    HTTPException,
)

from backend.services.dependencies import (
    DependencyUnavailable,
    ExternalOperationFailed,
)
from backend.services.ticket_sync import (
    get_ticket_sync_state,
    sync_all_tickets,
)


router = APIRouter(
    prefix="/api/ticket-sync",
    tags=["ticket-sync"],
)

@router.get("/sync")
def ticket_sync_state():

    return get_ticket_sync_state()


@router.post("/sync")
def sync_tickets():

    try:
        return sync_all_tickets()

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
            detail="Ticket sync timed out.",
        )

    except ExternalOperationFailed as error:
        raise HTTPException(
            status_code=503,
            detail={"code": error.code, "message": error.message},
        ) from None

    except RuntimeError:
        raise HTTPException(
            status_code=502,
            detail="The noc-tools sync operation failed.",
        ) from None