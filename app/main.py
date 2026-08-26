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

# Comma-separated CORS_ALLOWED_ORIGINS overrides the single-origin default so
# production can allow the deployed frontend domain without a code change;
# unset (the local-dev default) falls back to [frontend_url] unchanged.
_cors_origins = (
    [origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()]
    or [settings.frontend_url]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
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

from app.jira.router import oauth_router as jira_oauth_router
from app.jira.router import router as jira_router

app.include_router(jira_oauth_router, prefix="/jira", tags=["jira-oauth"])
app.include_router(jira_router, prefix="/api/jira", tags=["jira"])

from app.rag.router import router as knowledge_router

app.include_router(knowledge_router, prefix="/api/knowledge", tags=["knowledge"])

from app.tickets.router import router as tickets_router
from app.tickets.store import init_db as _init_tickets_db

app.include_router(tickets_router, prefix="/api/tickets", tags=["tickets"])


@app.on_event("startup")
def _init_tickets_store() -> None:
    """Create data/tickets.db and its table if they don't already exist."""
    _init_tickets_db()
