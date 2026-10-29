import subprocess

from fastapi import (
    APIRouter,
    HTTPException,
)

from pydantic import BaseModel

from backend.services.jira_create import (
    build_description,
    create_jira_ticket,
    preview_jira_ticket,
)



router = APIRouter(
    prefix="/api/jira/tickets",
    tags=["jira-create"],
)


class JiraTicketPreviewRequest(BaseModel):
    summary: str
    tenant: str = ""
    customer: str = ""
    device: str = ""
    deviceType: str = ""
    deviceId: str = ""
    component: str = ""
    salesforceTicket: str = ""
    issueDetails: str
    technicalFindings: str = ""
    steps: list[str] = []

class JiraTicketCreateRequest(
    JiraTicketPreviewRequest
):
    confirmed: bool = False    


@router.post("/preview")
def preview_ticket(
    request: JiraTicketPreviewRequest,
):

    description = build_description(
        tenant=request.tenant,
        customer=request.customer,
        device=request.device,
        device_type=request.deviceType,
        device_id=request.deviceId,
        component=request.component,
        salesforce_ticket=request.salesforceTicket,
        issue_details=request.issueDetails,
        technical_findings=request.technicalFindings,
        steps=request.steps,
    )

    try:
        return preview_jira_ticket(
            request.summary,
            description,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Jira preview timed out.",
        )

    except RuntimeError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )

@router.post("/create")
def create_ticket(
    request: JiraTicketCreateRequest,
):

    if request.confirmed is not True:
        raise HTTPException(
            status_code=409,
            detail=(
                "Explicit confirmation is required "
                "before creating a Jira ticket."
            ),
        )

    description = build_description(
        tenant=request.tenant,
        customer=request.customer,
        device=request.device,
        device_type=request.deviceType,
        device_id=request.deviceId,
        component=request.component,
        salesforce_ticket=request.salesforceTicket,
        issue_details=request.issueDetails,
        technical_findings=request.technicalFindings,
        steps=request.steps,
    )

    try:
        return create_jira_ticket(
            request.summary,
            description,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Jira creation timed out.",
        )

    except RuntimeError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )    