from datetime import date

from fastapi import APIRouter, HTTPException

from backend.services.health import get_health


router = APIRouter(
    prefix="/api/health",
    tags=["health"],
)


@router.get("/{shift_date}")
def health(shift_date: str):
    try:
        date.fromisoformat(shift_date)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="shift_date must use YYYY-MM-DD format",
        )

    return get_health(shift_date)