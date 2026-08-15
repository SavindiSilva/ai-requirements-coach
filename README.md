# AI Requirements Coach

An AI assistant that helps startup software teams turn vague Jira tickets
into development-ready requirements through an interactive coaching
conversation, grounded in company-specific context via RAG.

## Day 1 setup checklist

1. **Create a virtual environment and install dependencies**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate      # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Create a Supabase project** at https://supabase.com
   - Copy the Project URL and anon/public key into `.env` as
     `SUPABASE_URL` / `SUPABASE_KEY`
   - Copy the service_role key (Settings -> API) into
     `SUPABASE_SERVICE_ROLE_KEY` — backend only, never expose this to the
     frontend
   - Copy the Postgres connection string into `DATABASE_URL`

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
  auth/        Supabase-auth-backed session handling
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

## Build order (matches the locked plan)

1. Project skeleton + health check (this commit)
2. Jira OAuth app registration + sandbox project
3. DoR evaluation prompt, tested standalone against sample tickets
4. LangGraph state machine wrapping evaluation into the coaching loop
5. RAG (ChromaDB + embeddings + retrieval)
6. Jira read/write integration
7. Frontend
