from datetime import date

from fastapi import APIRouter, HTTPException

from backend.services.start_shift import (
    get_start_shift_preflight,
    start_shift,
)


router = APIRouter(
    prefix="/api/start-shift",
    tags=["start-shift"],
)


@router.get("/{shift_date}")
def start_shift_preflight(
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

    return get_start_shift_preflight(
        shift_date
    )

@router.post("/{shift_date}")
def execute_start_shift(
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

    preflight = get_start_shift_preflight(
        shift_date
    )

    if not preflight["ready"]:
        raise HTTPException(
            status_code=409,
            detail=(
                "Start Shift blocked because "
                "required tools are missing."
            ),
        )

    try:
        return start_shift(
            shift_date
        )

    except OSError as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Start Shift filesystem "
                f"operation failed: {error}"
            ),
        )

    except RuntimeError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        )