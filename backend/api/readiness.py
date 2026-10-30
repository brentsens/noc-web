from datetime import date

from fastapi import APIRouter, HTTPException

from backend.config import ConfigurationError, resolve_readiness_profile
from backend.services.readiness import assess_readiness, configuration_failure


router = APIRouter(prefix="/api/readiness", tags=["readiness"])


@router.get("/{shift_date}")
def readiness(shift_date: str):
    try:
        date.fromisoformat(shift_date)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="shift_date must use YYYY-MM-DD format",
        ) from None

    try:
        profile = resolve_readiness_profile()
    except ConfigurationError as error:
        raise HTTPException(
            status_code=422,
            detail={
                "overallStatus": "notReady",
                "configuration": configuration_failure(error.setting).serialize(),
                "checks": [],
                "liveness": [],
            },
        ) from None
    return assess_readiness(profile, shift_date)
