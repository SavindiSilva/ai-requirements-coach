"""
Central configuration for AI Requirements Coach.

All secrets and environment-specific values are read from environment
variables (via a local .env file in development). Nothing here should
ever be hardcoded, and this file should never contain real keys.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    app_name: str = "AI Requirements Coach"
    environment: str = "development"  # development | production
    frontend_url: str = "http://localhost:3000"

    # --- Supabase (database + auth) ---
    # Using the new publishable/secret key system (anon/service_role are
    # being deprecated by end of 2026) — see Supabase docs on migrating.
    supabase_url: str = ""
    supabase_publishable_key: str = ""  # safe for frontend, replaces anon key
    supabase_secret_key: str = ""       # backend-only, replaces service_role, bypasses RLS
    database_url: str = ""  # direct Postgres connection string, for SQLAlchemy

    # --- LLM (Claude) ---
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-5"

    # --- Embeddings ---
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"

    # --- Vector DB (ChromaDB) ---
    chroma_persist_dir: str = "./chroma_data"

    # --- Jira OAuth 2.0 (3LO) ---
    jira_client_id: str = ""
    jira_client_secret: str = ""
    jira_redirect_uri: str = "http://localhost:8000/jira/callback"
    # write:jira-work is required for the explicit-approval Jira update flow
    # (app/jira/client.py::update_issue) - CLAUDE.md section 17 requires
    # explicit user approval before any write, enforced at the UI/endpoint
    # level (never automatic), not by withholding the scope.
    jira_scopes: str = "read:jira-work write:jira-work offline_access"

    # --- Coaching loop tuning (matches locked spec) ---
    max_clarification_rounds: int = 5
    readiness_pass_threshold: int = 2  # criterion score >= this counts as "ready"


settings = Settings()
