from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr

from backend.services.assistant import (
    AssistantQuestion,
    answer,
    validate_assistant_response,
    validate_question,
    validate_shift_date,
)
from backend.services import ai_reports
from backend.services.ai_provider import (
    PROVIDER_DEEPSEEK,
    PROVIDER_OLLAMA,
    provider_readiness,
    provider_timeout_seconds_for,
    resolve_provider_runtime_for,
)
from backend.services.assistant_actions import AI_ACTIONS
from backend.services.local_retry import (
    RetrySnapshotError,
    capture_local_retry,
    get_retry_store,
    resolve_retry_runtime,
)


router = APIRouter(prefix="/api/shifts", tags=["assistant"])


def _provider_state(runtime: Request) -> tuple[object, str]:
    provider = getattr(runtime.app.state, "assistant_provider", None)
    identifier = getattr(runtime.app.state, "assistant_provider_identifier", None)
    if identifier is None:
        readiness = provider_readiness()
        code = (
            "assistant-provider-not-configured"
            if readiness.get("readiness") == "notConfigured"
            else "assistant-provider-not-ready"
        )
        message = (
            "The assistant provider is not configured."
            if code == "assistant-provider-not-configured"
            else "The assistant provider is not ready."
        )
        raise HTTPException(
            status_code=503,
            detail={"code": code, "message": message},
        )
    if provider is None or not callable(provider):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "assistant-provider-not-ready",
                "message": "The assistant provider is not ready.",
            },
        )
    return provider, identifier


class AssistantQuestionRequest(BaseModel):
    shiftDate: StrictStr
    question: StrictStr
    providerDisclosureAcknowledged: StrictBool
    provider: StrictStr | None = None


class AssistantActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    providerDisclosureAcknowledged: StrictBool
    provider: StrictStr | None = None


class LocalRetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retryToken: StrictStr
    confirmed: StrictBool


def _requested_provider(runtime: Request, requested: str | None):
    if requested is None:
        return _provider_state(runtime)
    if requested not in {PROVIDER_DEEPSEEK, PROVIDER_OLLAMA}:
        raise HTTPException(
            status_code=422,
            detail="provider must be deepseek-api or ollama.",
        )
    selected = resolve_provider_runtime_for(requested)
    readiness = selected.readiness if isinstance(selected.readiness, dict) else {}
    if selected.provider is None:
        code = (
            "assistant-provider-not-configured"
            if readiness.get("readiness") == "notConfigured"
            else "assistant-provider-not-ready"
        )
        raise HTTPException(
            status_code=503,
            detail={
                "code": code,
                "message": "The selected assistant provider is not ready.",
            },
        )
    if readiness.get("readiness") != "ready":
        raise HTTPException(
            status_code=503,
            detail={
                "code": "assistant-provider-not-ready",
                "message": "The selected assistant provider is not ready.",
            },
        )
    return selected.provider, selected.identifier


def _retry_error(error: RetrySnapshotError) -> HTTPException:
    return HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": error.message},
    )


def _capture_retry(workflow: str, shift_date: str, identity: str | None, prepared):
    availability = capture_local_retry(
        workflow=workflow,
        shift_date=shift_date,
        identity=identity,
        payload=prepared,
    )
    return availability


def _retry_response(
    shift_date: str,
    request: LocalRetryRequest,
    *,
    workflow: str,
    identity: str | None = None,
):
    if request.confirmed is not True:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "retry-confirmation-required",
                "message": "Explicit confirmation is required for local retry.",
            },
        )
    try:
        snapshot = get_retry_store().consume(
            request.retryToken,
            workflow=workflow,
            shift_date=shift_date,
            identity=identity,
        )
        runtime = resolve_retry_runtime()
    except RetrySnapshotError as error:
        raise _retry_error(error) from None
    question = AssistantQuestion(
        shift_date,
        str(snapshot.get("payload", {}).get("envelope", {}).get("question", "")),
        True,
    )
    response = answer(
        question,
        provider=runtime.provider,
        provider_identifier=runtime.identifier,
        prepared=snapshot.get("payload"),
        provider_timeout=provider_timeout_seconds_for(runtime.identifier),
    )
    if not validate_assistant_response(
        response,
        shift_date,
        expected_provider=runtime.identifier,
    ):
        raise HTTPException(
            status_code=502,
            detail="Assistant response was invalid; no report was saved.",
        )
    return response


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
    provider, provider_identifier = _requested_provider(runtime, request.provider)
    retry_availability = {}
    response = answer(
        question,
        provider=provider,
        provider_identifier=provider_identifier,
        failure_hook=lambda prepared: retry_availability.update(
            _capture_retry(
                "assistant-action",
                validated_shift,
                action_type,
                prepared,
            ) or {}
        ),
        provider_timeout=provider_timeout_seconds_for(provider_identifier),
    )
    if not validate_assistant_response(
        response,
        validated_shift,
        expected_provider=provider_identifier,
    ):
        raise HTTPException(
            status_code=502,
            detail="Assistant response was invalid; no report was saved.",
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
            report_save_warning = (
                "Analysis completed, but its advisory report could not be saved."
            )
        except ai_reports.AIReportPersistenceError:
            report_save_warning = (
                "Analysis completed, but its advisory report could not be saved."
            )

    if retry_availability:
        response = {**response, "localRetry": retry_availability}
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
    provider, provider_identifier = _requested_provider(runtime, request.provider)
    retry_availability = {}
    response = answer(
        question,
        provider=provider,
        provider_identifier=provider_identifier,
        failure_hook=lambda prepared: retry_availability.update(
            _capture_retry(
                "assistant",
                validated_shift,
                None,
                prepared,
            ) or {}
        ),
        provider_timeout=provider_timeout_seconds_for(provider_identifier),
    )
    if not validate_assistant_response(
        response,
        validated_shift,
        expected_provider=provider_identifier,
    ):
        raise HTTPException(
            status_code=502,
            detail="Assistant response was invalid.",
        )
    if retry_availability:
        response = {**response, "localRetry": retry_availability}
    return response


@router.post("/{shift_date}/assistant/local-retry")
@router.post("/{shift_date}/assistant/questions/local-retry")
def retry_assistant_question(
    shift_date: str,
    request: LocalRetryRequest,
    runtime: Request,
):
    try:
        validated_shift = validate_shift_date(shift_date)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from None
    return _retry_response(
        validated_shift,
        request,
        workflow="assistant",
    )


@router.post("/{shift_date}/assistant/actions/{action_type}/local-retry")
def retry_assistant_action(
    shift_date: str,
    action_type: str,
    request: LocalRetryRequest,
    runtime: Request,
):
    try:
        validated_shift = validate_shift_date(shift_date)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from None
    action = AI_ACTIONS.get(action_type)
    if action is None:
        raise HTTPException(status_code=404, detail="Assistant action not found.")
    response = _retry_response(
        validated_shift,
        request,
        workflow="assistant-action",
        identity=action_type,
    )
    report = None
    report_save_warning = None
    try:
        report = ai_reports.persist_ai_action_report(
            validated_shift,
            action_type,
            response,
        )
    except ai_reports.AIReportInvalidResult:
        report_save_warning = "Analysis completed, but its advisory report could not be saved."
    except ai_reports.AIReportPersistenceError:
        report_save_warning = "Analysis completed, but its advisory report could not be saved."
    return {
        "assistant": response,
        "report": report,
        "reportSaveWarning": report_save_warning,
    }
