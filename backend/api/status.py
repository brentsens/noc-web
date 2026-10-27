from datetime import date

from fastapi import APIRouter, HTTPException

from backend.services.status import get_status


router = APIRouter(
    prefix="/api/status",
    tags=["status"],
)


@router.get("/{shift_date}")
def status(shift_date: str):
    try:
        date.fromisoformat(shift_date)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="shift_date must use YYYY-MM-DD format",
        )

    return get_status(shift_date)