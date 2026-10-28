import subprocess

from datetime import date

from fastapi import (
    APIRouter,
    HTTPException,
)

from backend.services.handover import (
    generate_handover,
    get_handover,
)

from backend.services.end_shift import (
    get_end_shift_preflight,
)


router = APIRouter(
    prefix="/api/shifts",
    tags=["handover"],
)


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

@router.post("/{shift_date}/handover")
def create_handover(
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
            shift_date
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