from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr

from backend.services.ticket_sync import sync_local_ticket
from backend.services.tickets import (
    close_tracking,
    create_tracking,
    get_open_ticket,
    get_open_tickets,
    get_ticket,
    reactivate_tracking,
    update_tracking,
)


router = APIRouter(prefix="/api/tickets", tags=["tickets"])


class _ConfirmedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: StrictBool


class CreateTrackingAction(_ConfirmedAction):
    jiraKey: StrictStr
    nextAction: StrictStr = ""
    nocNotes: StrictStr = ""


class UpdateTrackingAction(_ConfirmedAction):
    nextAction: StrictStr = ""
    nocNotes: StrictStr = ""


def _action_error(error: Exception) -> HTTPException:
    if isinstance(error, FileExistsError):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, LookupError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, (ValueError, RuntimeError)):
        return HTTPException(status_code=422, detail=str(error))
    return HTTPException(status_code=500, detail="Local ticket tracking failed.")


@router.get("")
def tickets():
    return {"tickets": get_open_tickets()}


@router.get("/{ticket_id}")
def ticket(ticket_id: str):
    result = get_ticket(ticket_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return result


@router.post("/tracking")
def create_ticket_tracking(action: CreateTrackingAction):
    try:
        return create_tracking(
            action.jiraKey,
            action.nextAction,
            action.nocNotes,
            action.confirmed,
        )
    except Exception as error:
        raise _action_error(error) from error


@router.patch("/{ticket_id}/tracking")
def update_ticket_tracking(
    ticket_id: str,
    action: UpdateTrackingAction,
):
    try:
        return update_tracking(
            ticket_id,
            action.nextAction,
            action.nocNotes,
            action.confirmed,
        )
    except Exception as error:
        raise _action_error(error) from error


@router.post("/{ticket_id}/tracking/sync")
def sync_ticket_tracking(
    ticket_id: str,
    action: _ConfirmedAction,
):
    try:
        return sync_local_ticket(ticket_id, action.confirmed)
    except Exception as error:
        raise _action_error(error) from error


@router.post("/{ticket_id}/tracking/close")
def close_ticket_tracking(
    ticket_id: str,
    action: _ConfirmedAction,
):
    try:
        return close_tracking(ticket_id, action.confirmed)
    except Exception as error:
        raise _action_error(error) from error


@router.post("/{ticket_id}/tracking/reactivate")
def reactivate_ticket_tracking(
    ticket_id: str,
    action: _ConfirmedAction,
):
    try:
        return reactivate_tracking(ticket_id, action.confirmed)
    except Exception as error:
        raise _action_error(error) from error
