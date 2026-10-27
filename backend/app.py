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


app = FastAPI(
    title="SES NOC Operations API",
    version="0.1.0",
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

app.mount(
    "/",
    StaticFiles(
        directory=FRONTEND_ROOT,
        html=True,
    ),
    name="frontend",
)

