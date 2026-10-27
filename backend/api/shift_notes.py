from datetime import date

from fastapi import APIRouter, HTTPException

from backend.services.shift_notes import get_shift_notes


router = APIRouter(
    prefix="/api/shifts",
    tags=["shift-notes"],
)


@router.get("/{shift_date}/notes")
def shift_notes(shift_date: str):

    try:
        date.fromisoformat(shift_date)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="shift_date must use YYYY-MM-DD format",
        )

    return get_shift_notes(
        shift_date
    )