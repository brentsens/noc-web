from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.shift_notes import (
    add_shift_note,
    get_shift_notes,
)



router = APIRouter(
    prefix="/api/shifts",
    tags=["shift-notes"],
)

class ShiftNoteRequest(BaseModel):
    category: str
    text: str

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

@router.post("/{shift_date}/notes")
def create_shift_note(
    shift_date: str,
    request: ShiftNoteRequest,
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
        return add_shift_note(
            shift_date,
            request.category,
            request.text,
        )

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except OSError as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Could not save shift note: "
                f"{error}"
            ),
        )