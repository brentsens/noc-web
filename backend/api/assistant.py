from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr

from backend.services.assistant import (
    AssistantQuestion,
    answer,
    validate_question,
    validate_shift_date,
)
from backend.services import ai_reports
from backend.services.assistant_actions import AI_ACTIONS


router = APIRouter(prefix="/api/shifts", tags=["assistant"])


class AssistantQuestionRequest(BaseModel):
    shiftDate: StrictStr
    question: StrictStr
    providerDisclosureAcknowledged: StrictBool


class AssistantActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    providerDisclosureAcknowledged: StrictBool


@router.post("/{shift_date}/assistant/actions/{action_type}")
def run_assistant_action(
    shift_date: str,
    action_type: str,
    request: AssistantActionRequest,
    runtime: Request,
):
    try:
        validated_shift = validate_shift_date(shift_date)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from None
    action = AI_ACTIONS.get(action_type)
    if action is None:
        raise HTTPException(status_code=404, detail="Assistant action not found.")
    if request.providerDisclosureAcknowledged is not True:
        raise HTTPException(
            status_code=422,
            detail="Provider disclosure acknowledgement is required.",
        )

    question = AssistantQuestion(
        validated_shift,
        action.question,
        request.providerDisclosureAcknowledged,
    )
    provider = getattr(runtime.app.state, "assistant_provider", None)
    response = answer(question) if provider is None else answer(question, provider=provider)
    if (
        not isinstance(response, dict)
        or response.get("shiftDate") != validated_shift
        or response.get("provider") != "github-copilot-cli"
        or response.get("providerStatus")
        not in {"success", "unavailable", "timeout", "invalid", "not-invoked"}
        or response.get("status") not in {"complete", "limited", "unavailable"}
        or not isinstance(response.get("providerInvoked"), bool)
        or (response.get("providerStatus") == "success")
        is not (response.get("status") == "complete")
        or (
            response.get("providerStatus") == "not-invoked"
            and (
                response.get("providerInvoked") is not False
                or response.get("status") != "limited"
            )
        )
        or (
            response.get("providerStatus") in {"timeout", "invalid"}
            and response.get("providerInvoked") is not True
        )
    ):
        raise HTTPException(
            status_code=502,
            detail="Assistant response could not be validated; no report was saved.",
        )

    report = None
    report_save_warning = None
    if response.get("providerStatus") == "success":
        try:
            report = ai_reports.persist_ai_action_report(
                validated_shift,
                action_type,
                response,
            )
        except ai_reports.AIReportInvalidResult:
            raise HTTPException(
                status_code=502,
                detail="Assistant response could not be validated; no report was saved.",
            ) from None
        except ai_reports.AIReportPersistenceError:
            report_save_warning = (
                "Analysis completed, but its advisory report could not be saved."
            )

    return {
        "assistant": response,
        "report": report,
        "reportSaveWarning": report_save_warning,
    }


@router.post("/{shift_date}/assistant/questions")
def ask_assistant(
    shift_date: str,
    request: AssistantQuestionRequest,
    runtime: Request,
):
    try:
        validated_shift = validate_shift_date(shift_date)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from None
    if request.shiftDate != validated_shift:
        raise HTTPException(status_code=400, detail="shiftDate must match the URL shift.")
    if request.providerDisclosureAcknowledged is not True:
        raise HTTPException(
            status_code=422,
            detail="Provider disclosure acknowledgement is required.",
        )
    try:
        question = AssistantQuestion(
            validated_shift,
            validate_question(request.question),
            request.providerDisclosureAcknowledged,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    provider = getattr(runtime.app.state, "assistant_provider", None)
    if provider is None:
        return answer(question)
    return answer(question, provider=provider)
