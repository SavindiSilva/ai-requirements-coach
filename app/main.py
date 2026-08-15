"""
AI Requirements Coach — backend entrypoint.

Run locally with:
    uvicorn app.main:app --reload

Module layout (modular monolith — one deployable app, clearly separated
internal modules, matching the locked architecture):

    app/
      auth/        -> Supabase-auth-backed session handling
      jira/         -> OAuth 2.0 (3LO) + Jira REST API client
      tickets/       -> importing/storing ticket snapshots
      analysis/      -> the 4-criterion DoR evaluation engine
      coaching/      -> the clarification conversation loop
      agent/         -> LangGraph workflow orchestration wrapping analysis+coaching
      rag/           -> company/project knowledge retrieval (ChromaDB)
      database/      -> DB models / session management
      core/          -> settings, shared config

Each module will expose its own APIRouter; they get included below as
they're built out. For Day 1, this is just a health check so we know
the skeleton runs end to end before adding real logic.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """Basic liveness check — confirms the app is up and config loaded."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
    }


# --- Routers get wired in here as each module is built ---
from app.analysis.router import router as analysis_router

app.include_router(analysis_router, prefix="/api", tags=["analysis"])

from app.coaching.router import router as coaching_router

app.include_router(coaching_router, prefix="/api", tags=["coaching"])

# from app.jira.router import router as jira_router
# from app.tickets.router import router as tickets_router
#
# app.include_router(jira_router, prefix="/jira", tags=["jira"])
# app.include_router(tickets_router, prefix="/tickets", tags=["tickets"])
