from datetime import date

from fastapi import (
    APIRouter,
    HTTPException,
)

from backend.services.handover import (
    get_handover,
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