from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr

from backend.services import datadog_incidents


class IncidentProjectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: StrictStr
    title: StrictStr
    state: StrictStr
    severity: StrictStr | None = None
    createdAt: StrictStr | None = None
    updatedAt: StrictStr | None = None
    summary: StrictStr | None = None
    url: StrictStr | None = None


class IncidentSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    incidents: list[IncidentProjectionResponse]
    count: StrictInt | None
    lastAttemptedAt: StrictStr | None
    lastSuccessfulAt: StrictStr | None
    freshness: Literal["current", "stale", "unavailable", "refreshing"]
    error: Literal[
        "copilot-unavailable",
        "provider-unavailable",
        "timeout",
        "invalid-response",
        "cache-unavailable",
    ] | None


router = APIRouter(
    prefix="/api/datadog",
    tags=["datadog-incidents"],
)


@router.get(
    "/incidents",
    response_model=IncidentSnapshotResponse,
    response_model_exclude_unset=True,
)
def read_incidents():
    return datadog_incidents.get_incident_snapshot()


@router.post(
    "/incidents/refresh",
    response_model=IncidentSnapshotResponse,
    response_model_exclude_unset=True,
)
def refresh_incidents():
    return datadog_incidents.request_refresh()
