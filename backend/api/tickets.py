from fastapi import APIRouter, HTTPException

from backend.services.tickets import (
    get_open_ticket,
    get_open_tickets,
)


router = APIRouter(
    prefix="/api/tickets",
    tags=["tickets"],
)


@router.get("")
def tickets():
    return {
        "tickets": get_open_tickets()
    }


@router.get("/{ticket_id}")
def ticket(ticket_id: str):

    result = get_open_ticket(
        ticket_id
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found",
        )

    return result