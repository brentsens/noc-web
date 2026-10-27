from datetime import date

from fastapi import (
    APIRouter,
    HTTPException,
)

from backend.services.investigations import (
    get_investigation,
    get_investigations,
)


router = APIRouter(
    prefix="/api/shifts",
    tags=["investigations"],
)


def validate_shift_date(
    shift_date: str,
) -> None:

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


@router.get(
    "/{shift_date}/investigations"
)
def investigations(
    shift_date: str,
):

    validate_shift_date(
        shift_date
    )


    results = get_investigations(
        shift_date
    )


    return {
        "shiftDate":
            shift_date,

        "count":
            len(results),

        "investigations":
            results,
    }


@router.get(
    "/{shift_date}/investigations/"
    "{investigation_name}"
)
def investigation(
    shift_date: str,
    investigation_name: str,
):

    validate_shift_date(
        shift_date
    )


    result = get_investigation(
        shift_date,
        investigation_name,
    )


    if result is None:

        raise HTTPException(
            status_code=404,
            detail=(
                "Investigation not found"
            ),
        )


    return result
