from datetime import date

from fastapi import (
    APIRouter,
    HTTPException,
)

from backend.services.end_shift import (
    get_end_shift_preflight,
)


router = APIRouter(
    prefix="/api/end-shift",
    tags=["end-shift"],
)


@router.get("/{shift_date}")
def end_shift_preflight(
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

    return get_end_shift_preflight(
        shift_date
    )