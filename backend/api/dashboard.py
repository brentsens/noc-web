from datetime import date

from fastapi import APIRouter, HTTPException

from backend.services.dashboard import get_dashboard


router = APIRouter(
    prefix="/api/dashboard",
    tags=["dashboard"],
)


@router.get("/{shift_date}")
def dashboard(shift_date: str):

    try:
        date.fromisoformat(shift_date)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="shift_date must use YYYY-MM-DD format",
        )

    return get_dashboard(shift_date)