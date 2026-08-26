<img src="frontend/public/favicon.svg" alt="ReqPilot logo" width="64" height="64" />

# ReqPilot

An AI assistant that helps startup software teams turn vague Jira tickets
into development-ready requirements through an interactive coaching
conversation, grounded in company-specific context via RAG.

"ReqPilot" is a display-name rename only — the repository, backend
package (`app/`), and all code identifiers are still `ai-requirements-coach`
/ "AI Requirements Coach" internally. Nothing outside frontend-visible
strings (page title, nav bar, login/dashboard copy) changed.

## Day 1 setup checklist

1. **Create a virtual environment and install dependencies**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate      # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Create a Supabase project** at https://supabase.com (used for real
   email/password authentication via Supabase Auth, frontend-only today —
   see "Authentication" below)
   - Copy the Project URL and publishable key (Settings -> API Keys tab,
     not "Legacy API Keys") into `.env` as `SUPABASE_URL` /
     `SUPABASE_PUBLISHABLE_KEY`
   - Copy the secret key into `SUPABASE_SECRET_KEY` — backend only, never
     expose this to the frontend
   - Copy the Postgres connection string into `DATABASE_URL`
   - Copy the same Project URL and publishable key into
     `frontend/.env` as `VITE_SUPABASE_URL` / `VITE_SUPABASE_PUBLISHABLE_KEY`
     (`cp frontend/.env.example frontend/.env`) — the frontend talks to
     Supabase Auth directly, not through the backend

3. **Get an Anthropic API key** and put it in `ANTHROPIC_API_KEY`

4. **Get an OpenAI API key** (for embeddings only) and put it in
   `OPENAI_API_KEY`

5. **Register a Jira OAuth 2.0 (3LO) app**
   - Go to https://developer.atlassian.com/console/myapps/
   - Create an app, add the "OAuth 2.0 (3LO)" feature
   - Set the callback URL to match `JIRA_REDIRECT_URI` below
   - Under Permissions, add the Jira API with scopes:
     `read:jira-work`, `write:jira-work`, `offline_access`
   - Copy the Client ID and Secret into `.env`

6. **Create a free Jira Cloud sandbox site** at
   https://www.atlassian.com/software/jira/free , create one test
   project, and add 2-3 sample tickets (e.g. an intentionally vague one
   like "Add notification feature")

7. **Copy the env template and fill it in**
   ```bash
   cp .env.example .env
   ```

8. **Run the server**
   ```bash
   uvicorn app.main:app --reload
   ```
   Then check http://localhost:8000/health — you should see
   `{"status": "ok", ...}`

## Project structure

```
app/
  auth/        empty stub — no backend session/token verification yet;
               real login is Supabase Auth, enforced entirely on the
               frontend (see "Authentication" below)
  jira/        OAuth 2.0 (3LO) + Jira REST API client
  tickets/     importing/storing ticket snapshots
  analysis/    the 4-criterion Definition of Ready evaluation engine
  coaching/    the clarification conversation loop
  agent/       LangGraph workflow orchestration wrapping analysis+coaching
  rag/         company/project knowledge retrieval (ChromaDB)
  database/    DB models / session management
  core/        settings, shared config
```

This is a modular monolith: one deployable FastAPI app, cleanly split
into modules internally — not a microservices setup.

## Definition of Ready criteria (locked)

Each ticket is scored 0-3 on four criteria:

| Score | Meaning |
|---|---|
| 0 | Missing |
| 1 | Partial |
| 2 | Mostly Clear |
| 3 | Complete |

Criteria: Description Clarity, Acceptance Criteria, Open Questions, Scope
Definition.

Coaching loop stops when all four criteria score >= 2, or after a
maximum of 5 clarification questions (see `app/core/config.py`).

## Authentication

Real Supabase Auth (email/password sign-up, sign-in, sign-out) is
implemented in the frontend (`frontend/src/lib/auth.tsx`,
`frontend/src/lib/supabaseClient.ts`) — this is no longer a decorative
login screen. Two important limits to be aware of:

- **Frontend-enforced only.** The backend does not verify Supabase
  session tokens on any request; every `/api/*` endpoint is reachable by
  anyone who can reach the backend directly. Logging in only gates the
  frontend UI.
- **No per-user data scoping.** All accounts currently share the same
  backend-side state: one Jira connection, one SQLite reviewed-ticket
  history, one set of coaching sessions. There is no `user_id` anywhere
  in the schema. See `docs/architecture.md` §14 for the full picture.

## Deployment

The app is deployed with the frontend on Vercel, the backend on Render,
and the existing Supabase project for auth. The same codebase runs
locally and in production — only environment variables differ.

**Backend (Render)**
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  (single process — the SQLite ticket store isn't safe for concurrent
  writes from multiple workers, so don't add `--workers`)
- Mount a persistent disk and point `TICKETS_DB_PATH` and
  `CHROMA_PERSIST_DIR` at paths under it — Render's filesystem is
  otherwise ephemeral, and both defaults (`./data/tickets.db`,
  `./chroma_data`) would be wiped on every deploy/restart
- Set `CORS_ALLOWED_ORIGINS` to the deployed frontend's URL(s)
  (comma-separated for more than one; falls back to `frontend_url`,
  the local-dev default, if unset)
- Set `JIRA_REDIRECT_URI` to the production callback URL — Atlassian
  supports registering multiple callback URLs on one app, so the
  production URL can be added alongside the localhost one without
  breaking local dev
- Set the remaining secrets from `.env.example`
  (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `SUPABASE_*`, `DATABASE_URL`,
  `JIRA_CLIENT_ID`/`JIRA_CLIENT_SECRET`)

**Frontend (Vercel)**
- Set `VITE_API_BASE_URL` to the Render backend's URL
- Set `VITE_SUPABASE_URL` / `VITE_SUPABASE_PUBLISHABLE_KEY` to the same
  Supabase project used by the backend

## Build order (matches the locked plan)

1. Project skeleton + health check (this commit)
2. Jira OAuth app registration + sandbox project
3. DoR evaluation prompt, tested standalone against sample tickets
4. LangGraph state machine wrapping evaluation into the coaching loop
5. RAG (ChromaDB + embeddings + retrieval)
6. Jira read/write integration
7. Frontend
