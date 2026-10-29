import subprocess

from fastapi import (
    APIRouter,
    HTTPException,
)

from backend.services.jira_discovery import (
    get_open_jira_tickets,
)

from backend.services.jira_ticket_queue import (
    get_jira_ticket_queue,
    refresh_jira_ticket_queue,
)


router = APIRouter(
    prefix="/api/jira",
    tags=["jira-discovery"],
)


@router.get("/tickets")
def open_jira_tickets():

    try:
        return get_open_jira_tickets()

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Jira discovery timed out.",
        )

    except RuntimeError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )

@router.get("/ticket-queue")
def jira_ticket_queue():

    try:
        return get_jira_ticket_queue()

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Jira queue refresh timed out.",
        )

    except RuntimeError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )

@router.post("/ticket-queue/refresh")
def refresh_ticket_queue():

    try:

        return refresh_jira_ticket_queue()

    except FileNotFoundError as error:

        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except subprocess.TimeoutExpired:

        raise HTTPException(
            status_code=504,
            detail="Jira queue refresh timed out.",
        )

    except RuntimeError as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )