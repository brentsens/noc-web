from fastapi import FastAPI
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
from backend.api.assistant import (
    router as assistant_router,
)
from backend.services.copilot_cli import answer_with_copilot_cli
from backend.services.copilot_mcp import CopilotProvider

app = FastAPI(
    title="SES NOC Operations API",
    version="0.1.0",
)
app.state.assistant_provider = answer_with_copilot_cli


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
