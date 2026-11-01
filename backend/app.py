import logging
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import FRONTEND_ROOT

from backend.api.dashboard import (
    router as dashboard_router,
)

from backend.api.tickets import (
    router as tickets_router,
)

from backend.api.shift_notes import (
    router as shift_notes_router,
)

from backend.api.investigations import (
    router as investigations_router,
)

from backend.api.ai_reports import (
    router as ai_reports_router,
)

from backend.api.handover import (
    router as handover_router,
)

from backend.api.status import (
    router as status_router,
)

from backend.api.health import (
    router as health_router,
)

from backend.api.start_shift import (
    router as start_shift_router,
)

from backend.api.end_shift import (
    router as end_shift_router,
)

from backend.api.handover_delivery import (
    router as handover_delivery_router,
)

from backend.api.ticket_sync import (
    router as ticket_sync_router,
)

from backend.api.jira_create import (
    router as jira_create_router,
)

from backend.api.jira_discovery import (
    router as jira_discovery_router,
)

from backend.api.readiness import (
    router as readiness_router,
)
from backend.api.datadog_incidents import (
    router as datadog_incidents_router,
)
from backend.api.assistant import (
    router as assistant_router,
)
from backend.services.copilot_cli import answer_with_copilot_cli
from backend.services.copilot_mcp import CopilotProvider


runtime_logger = logging.getLogger("noc_web.runtime")

app = FastAPI(
    title="SES NOC Operations API",
    version="0.1.0",
)
app.state.assistant_provider = answer_with_copilot_cli


@app.middleware("http")
async def safe_request_logging(request, call_next):
    started = time.monotonic()
    method = request.method if request.method in {
        "GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"
    } else "OTHER"
    try:
        response = await call_next(request)
    except Exception:
        route = request.scope.get("route")
        route_path = getattr(route, "path", "unmatched")
        duration_ms = max(0, int((time.monotonic() - started) * 1000))
        runtime_logger.error(
            "http_request method=%s route=%s status=500 duration_ms=%d error=unhandled",
            method,
            route_path,
            duration_ms,
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": {
                    "code": "internal-error",
                    "message": "The request could not be completed.",
                }
            },
        )
    route = request.scope.get("route")
    route_path = getattr(route, "path", "unmatched")
    duration_ms = max(0, int((time.monotonic() - started) * 1000))
    runtime_logger.info(
        "http_request method=%s route=%s status=%d duration_ms=%d",
        method,
        route_path,
        response.status_code,
        duration_ms,
    )
    return response


def configure_assistant_provider(provider: CopilotProvider | None) -> None:
    """Inject a provider, or restore the default local Copilot CLI adapter."""
    app.state.assistant_provider = (
        answer_with_copilot_cli if provider is None else provider
    )


@app.get("/api/health")
def api_health():
    return {
        "status": "healthy",
        "service": "noc-web",
        "version": "0.1.0",
    }

app.include_router(
    dashboard_router
)

app.include_router(
    tickets_router
)

app.include_router(
    shift_notes_router
)

app.include_router(
    investigations_router
)

app.include_router(
    ai_reports_router
)

app.include_router(
    handover_router
)

app.include_router(
    status_router
)

app.include_router(
    health_router
)

app.include_router(
    start_shift_router
)

app.include_router(
    end_shift_router
)

app.include_router(
    handover_delivery_router
)

app.include_router(
    ticket_sync_router
)

app.include_router(
    jira_create_router
)

app.include_router(
    jira_discovery_router
)

app.include_router(
    readiness_router
)

app.include_router(
    datadog_incidents_router
)

app.include_router(
    assistant_router
)


app.mount(
    "/",
    StaticFiles(
        directory=FRONTEND_ROOT,
        html=True,
    ),
    name="frontend",
)
