# Architecture — Current State

> This document describes what is **actually implemented** in the codebase today.
> It is derived from reading the source under `app/` and `tests/`, not from
> `CLAUDE.md`'s target design. Where the two disagree, that is called out
> explicitly rather than silently assumed. See `CLAUDE.md` for the intended
> end-state design and phased roadmap.

## 1. Current system architecture

A single FastAPI application (modular monolith, matching the CLAUDE.md
mandate — no microservices). There is no frontend integration yet and no
database yet. The only externally-facing pieces today are:

```
HTTP client (tests / curl / future frontend)
        ↓
   FastAPI app (app/main.py)
        ↓
 ┌──────────────┬──────────────┐
 │ analysis     │  coaching    │   ← APIRouters
 └──────┬───────┴──────┬───────┘
        ↓              ↓
   app/agent/graph.py (LangGraph, two-node:
                        retrieve_context → analyze_requirement)
        ↓                    ↓
        │              app/agent/rag_integration.py (fail-safe wrapper)
        │                    ↓
        │              app/rag/store.py::retrieve()
        │                    ↓
        │              chunking.py / embeddings.py (OpenAI API) / ChromaDB
        ↓
   app/agent/llm.py → Anthropic Claude API
```

Coaching state is held in a process-local Python dict
(`app/coaching/store.py`) — it does not survive a process restart and is not
shared across worker processes. There is no database connection anywhere in
the codebase.

`app/rag/` itself remains a separate, self-contained subsystem (its own
external dependency on OpenAI embeddings, its own persistent ChromaDB
store, no HTTP endpoint of its own — unchanged from Phase 3's first pass).
As of this Phase 3 continuation, `app/agent/graph.py` and
`app/coaching/router.py` now call into it — through
`app/agent/rag_integration.py`, not directly — using a temporary hardcoded
`project_id="default"` evaluation scope. See §11.

## 2. Current backend module structure

```
app/
├── main.py            FastAPI app, CORS, router wiring, /health
├── agent/              LangGraph orchestration + Claude client (shared)
│   ├── graph.py           two-node graph: retrieve_context → analyze_requirement
│   ├── llm.py             Anthropic client wrapper, forced tool-use
│   ├── prompts.py         analysis system/user prompt templates
│   ├── state.py           AgentState TypedDict
│   └── rag_integration.py Phase 3: fail-safe retrieval wrapper + temporary project_id="default"
├── analysis/           Phase 1: requirement analysis
│   ├── router.py         POST /api/analyse
│   └── schemas.py        TicketInput, AnalysisContent, AnalysisResult, ...
├── coaching/            Phase 2: multi-turn clarification loop
│   ├── router.py         /api/coaching/* endpoints (finalize now retrieves RAG context)
│   ├── schemas.py         request/response models
│   ├── state.py           CoachingSessionState TypedDict
│   ├── store.py           in-memory session store (dict), validation errors
│   ├── selection.py       deterministic weakest-criterion selection
│   ├── stop_condition.py  deterministic stop-condition + remaining-gaps logic
│   ├── llm.py             Claude wrappers for question/finalize generation
│   └── prompts.py         coaching prompt templates (finalize prompt now context-aware)
├── core/
│   └── config.py         pydantic-settings Settings (env-driven)
├── rag/                 Phase 3: standalone project-scoped RAG module (unchanged this pass)
│   ├── schemas.py         DocumentType, DocumentInput, ChunkMetadata, IngestResult, RetrievedChunk
│   ├── chunking.py         pure word-based chunk_text()
│   ├── embeddings.py       OpenAI embedding client wrapper, EmbeddingError
│   └── store.py            ChromaDB PersistentClient, add_document(), retrieve(), RAGStoreError
├── jira/                Jira OAuth 2.0 (3LO) + Jira Cloud REST API v3 read/write
│   ├── router.py          /jira/authorize, /jira/callback, /api/jira/* (two APIRouters)
│   ├── oauth.py           Atlassian token exchange/refresh + accessible-resources lookup
│   ├── client.py          authenticated Jira REST calls (projects/issues/issue detail/update)
│   ├── parsing.py         pure: ADF↔plain-text both directions, issuelinks/parent/subtasks→RelatedIssue,
│   │                       FinalRequirementContent→plain text for the update flow
│   ├── store.py           TEMPORARY in-memory connection + OAuth CSRF-state store
│   ├── schemas.py         JiraProject, JiraIssueSummary, JiraIssueDetail, JiraStatusResponse, JiraUpdateResponse
│   └── state.py           JiraConnectionState TypedDict
├── auth/                empty (__init__.py only) — not started
├── database/            empty (__init__.py only) — not started
└── tickets/             reviewed-ticket history, SQLite-backed (see §13)
    ├── router.py          POST/GET /api/tickets/reviewed
    ├── store.py           sqlite3-backed (data/tickets.db) + upsert-by-issue_key
    └── schemas.py         ReviewedTicket

tests/
├── test_analysis.py       Phase 1 endpoint tests (real Claude API, no mocks) — unchanged
├── test_coaching.py       Phase 2 endpoint + pure-logic tests — unchanged
├── test_rag.py             Phase 3 standalone RAG tests, plus list_documents() tests (§11)
├── test_rag_integration.py Phase 3 prompt-integration tests: deterministic prompt-construction
│                            and fail-safe-retrieval tests, plus one real-Claude-call regression test
├── test_knowledge_upload.py Upload endpoint tests, plus GET /api/knowledge/documents tests (§11)
├── test_jira.py            Jira module tests: pure parsing logic, in-memory store,
│                            monkeypatched-httpx OAuth/REST calls, endpoint tests, and
│                            deterministic related_issues prompt-wiring tests (see §12)
└── test_tickets.py         Reviewed-ticket history: in-memory store + endpoint tests (§13)

scripts/
└── rag_eval.py           manual, non-CI with-RAG vs. without-RAG comparison (not part of pytest)
```

`auth/` and `database/` exist only as empty package stubs (`__init__.py`
with zero content) - no code has been written in either. `tickets/` now
holds the reviewed-ticket history store (§13); `auth/` and `database/`
remain untouched.
`rag/` itself (chunking/embeddings/store/schemas) was not modified in this
pass — the RAG integration lives entirely in
`app/agent/rag_integration.py`, plus small additive changes to
`app/agent/graph.py`, `app/agent/prompts.py`, `app/coaching/prompts.py`,
and `app/coaching/router.py` (see §3, §4, §11). `app/jira/` is new (see
§12) and is unrelated to the RAG integration - it does not yet feed a real
`project_id` into it (see §12's "Not yet done" list).

## 3. Analysis flow (Phase 1)

Entry point: `POST /api/analyse` (`app/analysis/router.py`).

```
TicketInput {title, description}
        ↓
analyze_ticket()                       app/agent/graph.py
        ↓
LangGraph: START → retrieve_context_node → analyze_requirement_node → END
        ↓
retrieve_context_node:
  get_retrieved_context(f"{title}\n{description}")   app/agent/rag_integration.py
  — [] immediately if OPENAI_API_KEY unset; [] if retrieve() raises
    EmbeddingError/RAGStoreError/ValueError; never raises itself
  → state["retrieved_context"]
        ↓
build_system_prompt() + build_user_prompt(ticket, coaching_history,
                                            retrieved_context)   app/agent/prompts.py
  — appends a "Relevant project context" section only if retrieved_context
    is non-empty; identical output to pre-Phase-3 otherwise
  — appends a "Related Jira issues" section only if ticket.related_issues
    is non-empty (see §12) — told to Claude as confirmed, not inferred
        ↓
run_structured_analysis()               app/agent/llm.py
        ↓
Claude API call, forced tool-use (tool_choice pinned to
"submit_requirement_analysis", schema = AnalysisContent.model_json_schema())
        ↓
AnalysisContent.model_validate(tool_use.input)   — re-validated, never
                                                     trusted as raw text
        ↓
overall_readiness computed in Python (average of 4 criterion scores,
                                        never trusted from the LLM)
        ↓
AnalysisResult returned to caller
```

`analyze_ticket()` also accepts an optional `coaching_history:
list[tuple[str, str]]`, which — when present — is appended to the user
prompt as a "Previous clarification" section. This is what the coaching
re-analysis step (§4) reuses; the analysis code itself is unchanged whether
or not coaching history is supplied. `analyze_ticket()`'s own signature did
**not** change for Phase 3 RAG integration — it still takes only `ticket`
and `coaching_history`; the temporary `project_id="default"` is resolved
internally inside `retrieve_context_node`, so `app/analysis/router.py` and
every coaching call site needed zero changes to pick up retrieval.

## 4. Coaching flow (Phase 2)

Coaching state lives entirely in-memory (`app/coaching/store.py:_SESSIONS`),
keyed by a `uuid4` session id. There is no database-backed persistence.

```
POST /api/coaching/start  {title, description}
    → analyze_ticket() (same Phase 1 pipeline)
    → select_weakest_criterion()        deterministic, no LLM
    → gather_relevant_issues()          deterministic, no LLM
    → generate_clarification_question() Claude call, forced tool-use
    → create_session(...)               stores session in memory
    ← {session_id, question, why, current_scores}

POST /api/coaching/{id}/message  {answer}
    → record_answer()                   moves current_question into
                                          questions_asked/answers, no LLM call
    ← {question, answer, question_count, ..., current_scores}

POST /api/coaching/{id}/reanalyze
    → analyze_ticket(ticket, coaching_history=list(zip(questions, answers)))
    → replace_analysis()                overwrites session["analysis"]
    ← {analysis, question_count, questions_asked, answers}

POST /api/coaching/{id}/next
    → should_stop_coaching()            deterministic, no LLM:
                                          stop if question_count >= max_clarification_rounds
                                          OR min(4 criterion scores) >= readiness_pass_threshold
    → if stop:   mark_coaching_complete()
    → if not:    select_weakest_criterion() + generate_clarification_question()
                  → set_next_question()
    ← {is_complete, stop_reason, question?, why?, current_scores}

POST /api/coaching/{id}/finalize
    → requires session["is_complete"] == True
    → compute_remaining_gaps()          deterministic, no LLM
    → get_retrieved_context(f"{ticket.title}\n{ticket.description}")
                                          app/agent/rag_integration.py, same fail-safe wrapper
                                          as the analysis flow — fresh retrieval at finalize
                                          time, not reused from /start
    → generate_final_requirement()      Claude call, forced tool-use, prompt now includes
                                          a "Relevant project context" section if any chunks
                                          were retrieved
                                          (idempotent — cached on session after first call)
    ← {final_requirement, remaining_gaps, current_scores, ...}
```

`/start`, `/reanalyze`, and `/next` all pick up retrieval "for free" because
they call `analyze_ticket()`, which now runs the two-node graph described
in §3. `/finalize` is the one coaching step that never went through
`analyze_ticket()`, so it has its own direct `get_retrieved_context()` call
right before building its prompt.

The frontend (`frontend/src/routes/CoachingPage.tsx`) now consumes
`/finalize` directly: once a session's `is_complete` is `true`, a "View
Development-Ready Ticket" button calls it via a dedicated
`useFinalizeCoaching()` mutation
(`frontend/src/hooks/useFinalizeCoaching.ts`) and renders the result with
`frontend/src/components/coaching/FinalRequirementView.tsx`. No backend
change was needed — the existing `FinalizeResponse` contract already
carried everything the view needs (user story, acceptance criteria, scope,
assumptions, dependencies, remaining gaps, current scores). Because
`/finalize` is idempotent server-side (see §4 above), the frontend re-calls
it on retry after a failed attempt without any special-casing.

`generate_final_requirement()` (`app/coaching/llm.py`) is robust to a
specific malformed-output failure observed in production for tickets that
reach `max_questions_reached` with consistently vague coaching answers:
Claude occasionally collapses a list-typed field (`acceptance_criteria`,
`scope`, `assumptions`, or `dependencies`) into a plain string, and/or omits
`user_story` entirely. `normalize_final_requirement_input()` recovers both
shapes before Pydantic validation — a string value is wrapped as a
single-item list, and a missing/blank `user_story` is replaced with an
honest placeholder built from the ticket title — logging a warning
(including the field and `session_id`) whenever it fires, so real
occurrences stay visible rather than being silently patched over. Any other
malformed shape is left for Pydantic to reject normally, since there's
nothing safe to guess there. `_FINAL_REQUIREMENT_SYSTEM_PROMPT`
(`app/coaching/prompts.py`) also explicitly states the type contract (list
fields must always be a JSON array, `user_story` must always be present) as
complementary prevention — the coercion is what actually guarantees
`/finalize` never hard-fails on this input class, the prompt wording just
reduces how often it's needed.

Notes on what is **not** implemented in this flow:
- No user-approval endpoint (`POST /api/requirements/{id}/approve` from
  CLAUDE.md §24 does not exist).
- No Jira update step — finalize only returns the structured requirement;
  nothing writes it anywhere.
- The router docstring in `app/coaching/router.py` explicitly labels its
  steps "Phase 2A" through "Phase 2E", which matches this incremental build
  history.

## 5. LangGraph usage

One graph exists, now with two nodes:

```python
# app/agent/graph.py
START → retrieve_context_node → analyze_requirement_node → END
```

`retrieve_context_node` was added in this Phase 3 pass specifically
because retrieval-then-analyze is a genuine internal, in-process
transition (not a separate HTTP round-trip) — exactly the case where
expanding the graph is the right call, per the rule in `docs/skills.md`
§3. There is still no multi-node *coaching* graph — the "wait for user /
re-evaluate / more gaps?" loop described conceptually in CLAUDE.md §11 is
still implemented as plain FastAPI request/response endpoints in
`app/coaching/router.py` calling ordinary Python functions, **not** as
LangGraph nodes/edges, because each of those steps is a separate HTTP
round-trip driven by the user — that reasoning is unchanged by this pass.

`AgentState` (`app/agent/state.py`) is a `TypedDict` with `ticket`,
`analysis`, `coaching_history`, and now `retrieved_context` (Phase 3) — it
is reused by both nodes regardless of whether the call originates from
`/api/analyse` or from the coaching re-analysis step.

The graph is compiled once and memoized at module level (`_compiled_graph`
global, `get_graph()`).

## 6. Claude integration

- Single shared client: `app/agent/llm.py::get_client()` — lazily
  instantiates and memoizes one `anthropic.Anthropic(api_key=...)` client at
  module level. `app/coaching/llm.py` imports and reuses this same
  `get_client()` rather than creating its own client.
- Model is configured via `settings.claude_model` (currently defaults to
  `"claude-sonnet-5"`), read from `.env`/environment. No model name is
  hardcoded at call sites.
- **Structured output is always enforced via forced tool-use**, never via
  parsing free-form text:
  - Exactly one tool is offered per call.
  - `tool_choice = {"type": "tool", "name": <tool_name>}` forces that tool.
  - The tool's `input_schema` is generated directly from a Pydantic model
    via `Model.model_json_schema()`.
  - The returned `tool_use.input` is re-validated through the same Pydantic
    model (`Model.model_validate(...)`) before use — the LLM's output is
    never trusted as-is.
- Three call sites exist, all following this identical pattern:
  1. `run_structured_analysis()` → `AnalysisContent` (analysis)
  2. `generate_clarification_question()` → `ClarificationQuestionOutput` (coaching)
  3. `generate_final_requirement()` → `FinalRequirementContent` (coaching)
- Each call site wraps the Anthropic API call in `try/except Exception`,
  re-raising as a module-specific error (`LLMAnalysisError` /
  `CoachingLLMError`), and separately raises the same error type if the
  expected `tool_use` block is missing or fails validation.

## 7. API endpoints that currently exist

| Method | Path | Router | Purpose |
|---|---|---|---|
| GET | `/health` | `app/main.py` | Liveness check |
| POST | `/api/analyse` | `app/analysis/router.py` | Single-shot Phase 1 analysis |
| POST | `/api/coaching/start` | `app/coaching/router.py` | Analyse + ask first clarification question |
| POST | `/api/coaching/{session_id}/reanalyze` | `app/coaching/router.py` | Re-run analysis with accumulated Q&A |
| POST | `/api/coaching/{session_id}/message` | `app/coaching/router.py` | Record the user's answer |
| POST | `/api/coaching/{session_id}/next` | `app/coaching/router.py` | Decide stop-or-continue; ask next question if continuing |
| POST | `/api/coaching/{session_id}/finalize` | `app/coaching/router.py` | Generate the final development-ready requirement |
| GET | `/jira/authorize` | `app/jira/router.py` (`oauth_router`) | Redirect to Atlassian's OAuth consent screen |
| GET | `/jira/callback` | `app/jira/router.py` (`oauth_router`) | OAuth redirect target — exchanges code for tokens, stores connection |
| GET | `/api/jira/status` | `app/jira/router.py` | Whether a Jira connection is currently stored |
| GET | `/api/jira/projects` | `app/jira/router.py` | List accessible Jira projects |
| GET | `/api/jira/projects/{project_id}/issues` | `app/jira/router.py` | List issues in a project |
| GET | `/api/jira/issues/{issue_key}` | `app/jira/router.py` | Full issue detail, including related-issue links |
| GET | `/api/jira/issues/{issue_key}/links` | `app/jira/router.py` | Just the related-issue links for an issue |
| POST | `/api/jira/issues/{issue_key}/update` | `app/jira/router.py` | Overwrite an issue's description with the finalized requirement (description only - see §12) |
| POST | `/api/knowledge/upload` | `app/rag/router.py` | Ingest a company/project knowledge document (`document_type` optional, defaults to `general` - see §11) |
| GET | `/api/knowledge/documents` | `app/rag/router.py` | List the distinct documents already stored for a `project_id` (one entry per document, not per chunk - see §11) |
| POST | `/api/tickets/reviewed` | `app/tickets/router.py` | Record/upsert a reviewed ticket (see §13) |
| GET | `/api/tickets/reviewed` | `app/tickets/router.py` | List reviewed tickets, most recently upserted first (see §13) |

Endpoints listed in CLAUDE.md §24 that **do not exist yet**: `GET
/api/coaching/{session_id}` and `POST /api/requirements/{id}/approve` -
there is no separate persisted-approval endpoint (see §12 for how approval
is enforced instead).

## 8. Current state/persistence approach

- **No SQLAlchemy/Supabase database.** `app/database/` is an empty stub; no
  SQLAlchemy models, no Supabase client usage, no connection pooling
  anywhere in the code. The reviewed-ticket history (below) uses Python's
  built-in `sqlite3` directly against a local file — a deliberately minimal
  exception, not a general persistence layer.
- **Coaching sessions**: a single process-local `dict[str,
  CoachingSessionState]` in `app/coaching/store.py` (`_SESSIONS`). Explicitly
  documented in that module's docstring as a temporary placeholder — "does
  not survive process restarts and is not safe across multiple worker
  processes" — pending real DB-backed persistence.
- **Analysis results** (Phase 1, standalone `/api/analyse` calls): not
  persisted at all — returned directly in the HTTP response and discarded.
- **Jira connection**: a single process-local dict in `app/jira/store.py`
  (`_CONNECTION`) holding one OAuth token set + cloud id — explicitly
  documented in that module's docstring as "TEMPORARY SCAFFOLDING - NOT
  SUITABLE FOR PRODUCTION", mirroring the coaching store's caveat. Supports
  exactly one Jira connection process-wide (there is no user concept to
  scope it by yet); does not survive a restart.
- **Reviewed-ticket history**: SQLite-backed (`app/tickets/store.py`,
  `DB_PATH` = `data/tickets.db`, gitignored), upserted by `issue_key` so
  re-recording the same ticket (e.g. after coaching finishes) updates its
  row instead of duplicating it. Unlike the coaching/Jira-connection
  stores, this one does survive a backend restart — the only persistence
  in the app besides the RAG vector store (§13). Still not safe across
  multiple worker processes writing concurrently, and still unscoped by
  user (no auth system yet).
- **No auth**: `app/auth/` is an empty stub; there is no session/user
  concept, so coaching sessions, the Jira connection, and the reviewed-
  ticket history are not scoped to any user.

## 9. Configuration and external services

All configuration is centralized in `app/core/config.py` via
`pydantic_settings.BaseSettings`, reading from a local `.env` file
(`SettingsConfigDict(env_file=".env", extra="ignore")`). Mirrored in
`.env.example` with no real values.

Settings actually defined today:

| Setting | Used today? | Notes |
|---|---|---|
| `app_name`, `environment`, `frontend_url` | Yes | `app_name` in FastAPI title + `/health`; `frontend_url` in CORS `allow_origins` |
| `supabase_url`, `supabase_publishable_key`, `supabase_secret_key`, `database_url` | No | Declared, unused — no DB/auth code exists yet |
| `anthropic_api_key`, `claude_model` | Yes | Used by `app/agent/llm.py::get_client()` |
| `openai_api_key`, `embedding_model` | Yes | Used by `app/rag/embeddings.py::get_embedding_client()` — not yet used by anything outside `app/rag/` |
| `chroma_persist_dir` | Yes | Used by `app/rag/store.py::get_chroma_client()` (`chromadb.PersistentClient(path=...)`) |
| `jira_client_id`, `jira_client_secret`, `jira_redirect_uri`, `jira_scopes` | Yes | Used by `app/jira/oauth.py`; `jira_scopes` defaults to `"read:jira-work write:jira-work offline_access"` - `write:jira-work` was added for the issue-update flow (§12); a connection made before this change is read-only and must be reconnected (§8) to pick up the new scope |
| `max_clarification_rounds` | Yes | Used by `stop_condition.py` and the analysis system prompt (caps question count) |
| `readiness_pass_threshold` | Yes | Used by `stop_condition.py` (per-criterion stop bar, not `overall_readiness`) |

**External services actually called at runtime today:** the Anthropic
Claude API (analysis + coaching), the OpenAI embeddings API + a local
persistent ChromaDB instance, and now Atlassian's OAuth endpoints
(`auth.atlassian.com`) plus the Jira Cloud REST API v3
(`api.atlassian.com/ex/jira/{cloud_id}/...`) via `app/jira/`. The
OpenAI/ChromaDB pair fails safe (see below); the Jira calls do **not** fail
safe in the same way - `app/jira/router.py` translates
`JiraNotConnectedError` to `401` and `JiraAPIError`/`JiraOAuthError` to
`502`, since there is no "degrade gracefully" option for a user-initiated
Jira read or write (unlike RAG, which is optional background context).
Supabase/Postgres is still configured but not yet integrated or called
anywhere.

CORS is configured with a single allowed origin (`settings.frontend_url`),
all methods and headers, credentials allowed.

## 10. Current implementation status

| Area | Status | Evidence |
|---|---|---|
| Core AI analysis | **Implemented** | `app/analysis/`, `app/agent/`, `POST /api/analyse`, `tests/test_analysis.py` |
| Readiness scoring | **Implemented** | 4-criterion scoring + Python-computed `overall_readiness` in `app/agent/graph.py`; deterministic stop/gap logic in `app/coaching/stop_condition.py` |
| Coaching | **Implemented** | Full start → message → reanalyze → next → finalize loop in `app/coaching/`, covered by `tests/test_coaching.py` |
| Frontend integration | **Partially implemented** | `frontend/` (React + Vite): `POST /api/analyse`, the full coaching loop (`/start`, `/message`, `/reanalyze`, `/next`, `/finalize`), the Jira connect/project/issue flow, and now the "Approve & Update Jira" action on the finalized-requirement view are wired to real backend calls. `AppShell.tsx`'s login/nav state now persists to `sessionStorage` (§13) and reviewed-ticket history now lives in the backend (§13), so both survive a page refresh; an in-progress coaching session itself still does not (coaching state is backend-in-memory only, with no resume-by-`session_id` endpoint, and the Jira connection is still a single in-memory connection - both explicitly temporary, see §8). |
| Jira integration | **Implemented** — OAuth (3LO) + read APIs, in-memory connection | `app/jira/`, `tests/test_jira.py`, frontend `JiraImportFlow` (see §12). `read:jira-work write:jira-work offline_access`; connection storage is explicitly temporary scaffolding (§8). |
| RAG | **Implemented** — standalone module + API router + Jira-project-scoped prompt integration | `app/rag/`, `app/rag/router.py`, `app/agent/rag_integration.py`, `tests/test_rag.py`, `tests/test_rag_integration.py`, `tests/test_knowledge_upload.py`, `tests/test_knowledge_rag_e2e.py` — ingestion, embedding, retrieval, a knowledge-upload API router (`POST /api/knowledge/upload`), and analysis/coaching-finalize prompt integration are all implemented and tested. `TicketInput` now has a `project_id` field (see §11): for Jira-imported tickets it comes from the selected Jira project and is threaded into `retrieve_context_node`/`finalize_coaching_session`; **`TEMP_EVAL_PROJECT_ID = "default"`** remains only as the fallback for manually-entered tickets, which have no `project_id`. |
| Jira update | **Implemented** — description only, explicit user confirmation required | `POST /api/jira/issues/{issue_key}/update` (`app/jira/router.py`), `app/jira/client.py::update_issue()`, frontend confirm step in `FinalRequirementView.tsx` (see §12). No custom fields, assignee, priority, status, or story points are touched. No separate persisted-approval endpoint (CLAUDE.md §24's `POST /api/requirements/{id}/approve`) - the confirm step itself is the approval gate. |
| Deployment | **Not implemented** | No Dockerfile, no CI config, no Render/Vercel deployment config found in the repository |

Everything under `analysis/`, `coaching/`, `rag/` (including its
`app/agent/rag_integration.py` glue), and `jira/` is complete and tested
for its currently defined scope. RAG's scope is deliberately narrower than
the others in one specific way: it evaluates against a single, explicitly
temporary `project_id="default"` rather than real per-project context —
that narrower scope is itself fully implemented, not partially built.
Jira's scope is narrower in a different way: read-only, single in-memory
connection, no write/update endpoint (see §12). Everything else (`auth/`,
`database/`, `tickets/`) is an untouched empty stub.

## 11. RAG module (Phase 3: standalone module + evaluation-scoped prompt integration)

`app/rag/` is a self-contained subsystem for project-scoped document
ingestion and semantic retrieval — unchanged from its first Phase 3 pass
(see the ingestion/retrieval diagrams below). It is now also exposed over
HTTP via `app/rag/router.py` (`POST /api/knowledge/upload`).
What's new in this pass is that `analysis/` and `coaching/` now call into
it, through a dedicated glue module rather than directly.

```
DocumentInput {project_id, document_type, title, text}
        ↓
add_document()                          app/rag/store.py
        ↓
chunk_text()                            app/rag/chunking.py
  — pure, word-based, overlapping chunks (default: 200 words, 20-word overlap)
  — a document at or under the chunk size is returned as a single chunk
        ↓
embed_texts()                           app/rag/embeddings.py
  — OpenAI client, settings.embedding_model ("text-embedding-3-small")
  — raises EmbeddingError (never a raw exception) on API failure
        ↓
ChunkMetadata per chunk: {project_id, document_id, document_type, title, chunk_index}
        ↓
collection.add(ids, embeddings, documents, metadatas)   ChromaDB PersistentClient
  — persisted at settings.chroma_persist_dir, collection "project_documents"
        ↓
IngestResult {document_id, chunk_count}
```

```
retrieve(project_id, query_text, k=5, document_type=None)   app/rag/store.py
        ↓
project_id and query_text validated non-blank (raises ValueError if not)
        ↓
embed_text(query_text)                  app/rag/embeddings.py
        ↓
collection.query(query_embeddings=[...], n_results=k,
                  where={"project_id": project_id, ...})
  — project_id is always applied as a metadata filter; a document_type
    filter is added (via ChromaDB's "$and") only if the caller passes one
        ↓
list[RetrievedChunk] {text, metadata: ChunkMetadata, distance}
```

Key implementation details:
- **`project_id` isolation is enforced inside `retrieve()` itself**, not
  left to the caller — every query always includes a `project_id` filter,
  so a query scoped to one project can never structurally return another
  project's chunks (verified in
  `tests/test_rag.py::test_retrieve_project_id_filtering_prevents_cross_project_retrieval`).
- Two typed errors, following the same per-module narrow-exception
  convention as the rest of the codebase (see `docs/skills.md` §5):
  `EmbeddingError` (`app/rag/embeddings.py`, OpenAI call failures) and
  `RAGStoreError` (`app/rag/store.py`, ChromaDB read/write failures).
- The Chroma client and collection are lazily instantiated, module-level
  singletons (`get_chroma_client()`, `get_collection()`), matching the
  `get_client()` singleton pattern already used for the Anthropic client.
- `document_id` is caller-optional; `add_document()` generates a `uuid4` if
  none is supplied. Chunk ids are `f"{document_id}-{i}"`.
- No document-management layer exists (no update/delete) — only
  `add_document()` (create), `retrieve()` (query), and now `list_documents()`
  (list, see below). Still no update/delete, matching the "do not build a
  complicated document management system" constraint.
- An API router now exists: `app/rag/router.py`
  (`POST /api/knowledge/upload`, `GET /api/knowledge/documents`).
- `DocumentInput.document_type` is now **optional**, defaulting to
  `DocumentType.GENERAL` (a new enum member) when the caller doesn't supply
  one. The frontend's Knowledge panel no longer asks the user to categorize
  an upload (`KnowledgeContextPanel.tsx` dropped its Company/Project scope
  toggle and Document Type dropdown - see below); `document_type` itself is
  untouched in storage/metadata, it just isn't a required user choice
  anymore. `POST /api/knowledge/upload`'s `document_type` form field
  changed from `Form(...)` to `Form(DocumentType.GENERAL)` accordingly.
- `list_documents(project_id)` (`app/rag/store.py`) returns the **distinct
  set of documents** already stored for a project - one `DocumentSummary`
  {`document_id`, `title`, `document_type`} per document, not per chunk.
  Implemented as `collection.get(where={"project_id": project_id})`
  followed by de-duplication on `document_id` in Python (ChromaDB has no
  native "distinct" query). Same `project_id`-required-and-filtered
  invariant as `retrieve()` (raises `ValueError` for a blank `project_id`,
  `RAGStoreError` on a ChromaDB read failure). Exposed via
  `GET /api/knowledge/documents?project_id=...`, which
  `frontend/src/hooks/useKnowledgeDocuments.ts` calls on mount so
  `KnowledgeContextPanel.tsx` shows what's genuinely already stored for the
  selected project instead of starting from an empty local list; the
  upload mutation invalidates that query on success so a newly uploaded
  document appears without a manual refresh.
- `TicketInput` now has a `project_id` field (`app/analysis/schemas.py`). For
  Jira-imported tickets it's populated from the selected Jira project and
  threaded into retrieval via `app/agent/graph.py::retrieve_context_node`
  and `app/coaching/router.py::finalize_coaching_session` (coaching
  sessions carry it via `session["ticket"].project_id` — no separate field
  was added to `CoachingSessionState`). Manually-entered tickets have no
  `project_id`, so retrieval falls back to `TEMP_EVAL_PROJECT_ID`.

### Prompt integration: `app/agent/rag_integration.py`

This is the one new file that connects `app/rag/` to `analysis/`/
`coaching/`. It exists specifically so the connecting logic — the
temporary project scope and the fail-safe wrapper — lives in exactly one
place, rather than being duplicated at each call site (`app/agent/graph.py`
and `app/coaching/router.py`).

```
get_retrieved_context(query_text, project_id="default", k=5)
        ↓
if not settings.openai_api_key: return []           — never even attempts the call
        ↓
retrieve(project_id, query_text, k)                  app/rag/store.py, unmodified
        ↓
except (EmbeddingError, RAGStoreError, ValueError):  logs a warning, returns []
        ↓
list[RetrievedChunk]  (never raises)
```

```
format_context_for_prompt(chunks) -> str
  — "" for an empty list
  — otherwise: "Relevant project context (... supplementary, not
    authoritative ...):\n\n[document_type] title:\ntext\n\n..." for each chunk
```

**`TEMP_EVAL_PROJECT_ID = "default"`** is the one hardcoded project
identifier in the codebase — see CLAUDE.md §7 "Temporary evaluation scope"
for the full rationale and its required replacement path. It is resolved
internally by `get_retrieved_context()`'s default argument and by the two
call sites (`retrieve_context_node` in `app/agent/graph.py`,
`finalize_coaching_session()` in `app/coaching/router.py`) — it is never
accepted from any request schema, so `TicketInput`, `MessageRequest`, and
every other API contract are byte-for-byte unchanged from Phase 2.

**Two call sites, both going through `get_retrieved_context()`:**
1. `retrieve_context_node` (`app/agent/graph.py`) — the new first node in
   the analysis graph (see §3, §5). Covers `/api/analyse`,
   `/api/coaching/start`, and `/api/coaching/{id}/reanalyze`, since all
   three call `analyze_ticket()`.
2. `finalize_coaching_session()` (`app/coaching/router.py`) — a direct
   call right before `build_finalize_user_prompt()`, since `/finalize`
   never goes through `analyze_ticket()`/the graph. Retrieves fresh at
   finalize time (ticket title + description as the query), rather than
   reusing whatever was retrieved at `/start`.

**Fail-safe is the load-bearing property of this integration.** Before
this pass, `OPENAI_API_KEY` was not configured in the development
environment used to build Phase 3, meaning an unconditional retrieval call
would have broken every existing analysis/coaching test. `get_retrieved_context()`
short-circuits to `[]` before even attempting a call when the key is
unset, and separately catches `EmbeddingError`/`RAGStoreError`/`ValueError`
around the call regardless — so `analyze_ticket()` and `/finalize`
produce byte-for-byte the same prompts as before Phase 3 whenever no RAG
context is available, which is exactly why all pre-existing Phase 1/2
tests still pass unmodified (see `tests/test_rag_integration.py`'s
`test_retrieve_context_node_never_raises_when_rag_unavailable` and
`test_analyze_ticket_still_succeeds_when_rag_retrieval_raises`).

**Prompt shape change, only when context exists:** `build_user_prompt()`
(`app/agent/prompts.py`) and `build_finalize_user_prompt()`
(`app/coaching/prompts.py`) each gained an optional `retrieved_context`
parameter, appending a "Relevant project context" section via
`format_context_for_prompt()` — the same conditional-section pattern
already used for "Previous clarification." When `retrieved_context` is
`None` or `[]` (the case for every pre-Phase-3 caller and every call in
this environment without `OPENAI_API_KEY`), the section is omitted
entirely and the prompt is identical to before.

Tests:
- `tests/test_rag.py` (unchanged) — the standalone module, as before.
- `tests/test_rag_integration.py` (new) — deterministic prompt-construction
  tests (context section present/absent, using hand-built `RetrievedChunk`
  objects, no API calls), fail-safe behaviour tests for
  `get_retrieved_context()` and `retrieve_context_node` (monkeypatched
  failures), and one real-Claude-call regression test proving
  `analyze_ticket()` still succeeds when RAG retrieval raises.
- `tests/test_analysis.py`, `tests/test_coaching.py` — unmodified except
  one spy function signature in `test_coaching.py` (`_spy_build_user_prompt`
  in `test_coaching_finalize_prompt_receives_complete_context`) needed a new
  optional `retrieved_context=None` parameter to match
  `build_finalize_user_prompt()`'s new signature; the test's assertions are
  unchanged.

### With-RAG vs. without-RAG evaluation: `scripts/rag_eval.py`

A manual script, not part of the pytest suite — deliberately, since judging
whether retrieved context made an analysis *better* is a human read of the
output, not something to assert in CI given Claude's output is
non-deterministic. It seeds a few representative documents into
`project_id="default"`, then runs a couple of deliberately vague
representative tickets through analysis twice (retrieval forced on vs.
off) and prints both results side by side. Run with:

```
python -m scripts.rag_eval
```

If `OPENAI_API_KEY` is not configured, the script prints a warning and
still runs (seeding fails safely per-document, retrieval fails safe on
both runs) — the two runs will be identical in that case, which the
warning explains rather than leaving unexplained.

## 12. Jira module (OAuth 2.0 3LO + read/write APIs)

`app/jira/` connects the app to a real Jira Cloud site: OAuth login,
listing projects/issues, fetching one issue's full detail plus its
Jira-confirmed relationships, handing the selected issue into the
**unmodified** analysis/coaching pipeline via `TicketInput`, and - once a
requirement has been finalized and the user explicitly approves -
overwriting that issue's description with the finalized requirement (see
"Approving and writing back to Jira" below). No other Jira write ever
happens: no status transitions, no field beyond `description`, and CLAUDE.md
§17's separate persisted-approval step is intentionally not implemented
(see below for why).

### OAuth flow

```
Frontend "Connect Jira" button
        ↓ (full-page navigation, not fetch - OAuth needs a real browser redirect)
GET /jira/authorize                              app/jira/router.py (oauth_router)
        ↓
store.create_pending_state()                     app/jira/store.py - CSRF state, 10-min TTL
        ↓
oauth.build_authorize_url(state)                  app/jira/oauth.py
        ↓
302 → https://auth.atlassian.com/authorize (audience, client_id, scope,
                                              redirect_uri, state, response_type=code)
        ↓ user logs in / grants consent on Atlassian's own site
Atlassian redirects to JIRA_REDIRECT_URI (must exactly match the
                                            Atlassian Developer Console registration)
        ↓
GET /jira/callback?code=...&state=...             app/jira/router.py (oauth_router)
        ↓
store.validate_and_consume_state(state)            raises InvalidOAuthStateError -> 400
        ↓
oauth.exchange_code_for_tokens(code)                POST auth.atlassian.com/oauth/token,
                                                      then GET .../accessible-resources for cloud_id
                                                      raises JiraOAuthError -> 502
        ↓
store.save_connection(connection)                   app/jira/store.py
        ↓
302 → settings.frontend_url                         frontend re-checks /api/jira/status
```

`GET /jira/authorize` and `GET /jira/callback` are included in
`app/main.py` under `prefix="/jira"` (not `/api`), specifically because
`JIRA_REDIRECT_URI` (`http://localhost:8000/jira/callback` by default)
must match the callback path exactly, and that value is fixed by whatever
is registered in the Atlassian Developer Console - it cannot share the
`/api` prefix every other route in this app uses. The Jira *data* endpoints
(`/api/jira/*`) use a second `APIRouter` (`router`, distinct from
`oauth_router`) included under the normal `/api` prefix.

### Read APIs and token refresh

```
GET /api/jira/status                    -> {connected: store.is_connected()}
GET /api/jira/projects                  -> client.list_projects()
GET /api/jira/projects/{id}/issues      -> client.list_issues(project_id)   (JQL: project = "{id}")
GET /api/jira/issues/{key}              -> client.get_issue(key)
GET /api/jira/issues/{key}/links        -> client.get_issue_links(key)      (= get_issue(key).links)
```

`list_issues()` calls Jira's `GET /rest/api/3/search/jql`, not the older
`GET/POST /rest/api/3/search` - Atlassian removed the latter (410 Gone) as
part of its enhanced-JQL-search migration
([CHANGE-2046](https://developer.atlassian.com/changelog/#CHANGE-2046)).
The per-issue response shape (`issue.key`, `issue.fields.summary`, etc.) is
unchanged between the two endpoints, so `list_issues()`'s parsing logic
didn't need to change - only the path. Two behavioral differences from the
old endpoint that don't currently matter here: `fields` now defaults to
`id` only (this call already passed `fields` explicitly, so unaffected),
and pagination is `nextPageToken`-based rather than `startAt`/`total`-based
(this call only ever fetches one page via `maxResults=50` with no
pagination loop, so unaffected either way).

Every `client.py` call goes through `get_valid_connection()` first, which
transparently refreshes an expired access token
(`oauth.refresh_access_token()`, keeping the existing `cloud_id` rather
than re-fetching it) and persists the refreshed connection back to the
store before making the actual Jira REST call. `store.JiraNotConnectedError`
maps to `401`; `client.JiraAPIError`/`oauth.JiraOAuthError` map to `502` -
unlike RAG's fail-safe-to-empty pattern, a Jira read has no sensible
"degrade gracefully" behavior, so these are real errors surfaced to the
caller (see §9).

`app/jira/oauth.py` and `app/jira/client.py` use bare module-level
`httpx.get`/`httpx.post` calls rather than a persistent `httpx.Client`
singleton (unlike `app/agent/llm.py::get_client()` or
`app/rag/embeddings.py::get_embedding_client()`) - those hold a *static*
API key for the process lifetime, whereas the Jira bearer token changes
over time via refresh, so there is nothing worth caching in a long-lived
client.

### Parsing raw Jira data: `app/jira/parsing.py`

Two pure functions, no I/O, tested directly against hand-built fixture
dicts (same convention as `app/rag/chunking.py`):

- `adf_to_plain_text(node)` - Jira Cloud API v3 returns issue `description`
  as Atlassian Document Format (a rich-content JSON tree), not plain text.
  This does a best-effort recursive walk, joining text nodes and inserting
  a line break after each block-level node. Unknown ADF node types (tables,
  panels, etc.) are walked into but not specially formatted, so it degrades
  gracefully rather than raising.
- `extract_related_issues(fields)` - reads only what Jira itself reports:
  `issuelinks` (both `outwardIssue`/`inwardIssue` directions, using the
  link type's own `outward`/`inward` label as the relationship string),
  `parent`, and `subtasks`. Returns `RelatedIssue` objects (see below).
  Never infers a relationship Jira doesn't report - see CLAUDE.md §13.

### Confirmed relationships: `RelatedIssue` and `TicketInput.related_issues`

```python
# app/analysis/schemas.py - reused as-is by app/jira/schemas.py, not duplicated
class RelatedIssue(BaseModel):
    key: str
    relationship: str   # e.g. "blocks", "is blocked by", "relates to", "parent", "subtask"
    summary: str | None
```

`TicketInput` gained one new optional field:
`related_issues: list[RelatedIssue] | None = None`. This is additive and
backward-compatible - every pre-Jira caller (manual ticket entry, all
existing tests) constructs `TicketInput` without it and behaves exactly as
before. `JiraIssueDetail.links` (`app/jira/schemas.py`) uses the same
`RelatedIssue` model rather than a separate near-duplicate shape.

**Wired into the prompt, not just carried as data.** `build_user_prompt()`
(`app/agent/prompts.py`) appends a "Related Jira issues (confirmed by
Jira, not inferred)" section whenever `ticket.related_issues` is
non-empty - the same optional/backward-compatible conditional-section
pattern already used for `coaching_history` and RAG's `retrieved_context`
(see §3, §11, and `docs/skills.md` §9). The system prompt's dependency
guidance was also adjusted: it now tells Claude to treat a
`related_issues`-sourced relationship as a **confirmed** dependency, not a
possible one, while ticket-text-only dependencies (no Jira confirmation)
remain "possible" exactly as before. This is the same distinction CLAUDE.md
§13 draws between Jira-evidenced and LLM-inferred dependencies, now
actually reaching the LLM. No output schema changed - `AnalysisContent`
still only has `possible_dependencies`; a confirmed relationship shows up
in Claude's *reasoning* (its prose findings), not as a new structured
field, since restructuring the output schema was explicitly out of scope
for this slice.

Verified manually: with a fixture issue carrying a `blocks` relationship,
Claude's real analysis output described that dependency as "confirmed as
blocking" under its open-questions findings and left
`possible_dependencies` empty for it - i.e. it did not re-file the
Jira-confirmed relationship as merely possible.

### Frontend: `frontend/src/components/jira/JiraImportFlow.tsx`

A single component driving a local 3-step state machine (project list ->
issue list -> issue detail), following the codebase's existing
no-router, conditional-render convention (`ReviewTicketPage.tsx` already
switches between its manual form and the analysis-result view the same
way - see `docs/skills.md`). `ReviewTicketPage.tsx` gained a
`source: 'manual' | 'jira'` toggle; selecting "Import from Jira" renders
`JiraImportFlow` in place of the manual form. `JiraImportFlow`'s "Use This
Ticket" button calls the *exact same* `mutation.mutate(ticket)` the manual
form's submit handler calls - there is no parallel analysis/coaching
implementation for Jira-sourced tickets.

Four new React Query **read** hooks (`useJiraStatus`, `useJiraProjects`,
`useJiraProjectIssues`, `useJiraIssue`) are the first `useQuery` usage in
this codebase - every prior hook (`useAnalyseTicket`, `useStartCoaching`,
`useSubmitCoachingAnswer`, `useFinalizeCoaching`) is a `useMutation`, since
everything before this was a POST. `frontend/src/lib/api/client.ts` gained
`apiGet<T>()`, sharing response/error handling with `apiPost` via a new
private `handleResponse()` helper (both previously duplicated the same
`!response.ok` handling inline).

"Connect Jira" is a plain `window.location.href` navigation to
`${API_BASE_URL}/jira/authorize`, not a `fetch` call - OAuth requires a
real top-level browser redirect through Atlassian's own login/consent
pages, which a same-origin JSON API call cannot do.

### Approving and writing back to Jira

Once a session's finalized requirement carries a `source_issue_key`
(traced below), the frontend offers an "Approve & Update Jira" action.
CLAUDE.md §17 requires explicit user approval before any Jira write; this
implementation enforces that as a two-click, in-UI confirm step
(`FinalRequirementView.tsx`'s `showConfirm` state - click "Approve &
Update Jira", read the confirmation text naming the exact issue that will
be overwritten, click "Confirm & Update Jira") rather than a separate
persisted-approval endpoint (`POST /api/requirements/{id}/approve` from
CLAUDE.md §24 does not exist and isn't needed for this MVP - see §10).
Nothing writes to Jira until that second click fires the mutation; the
backend endpoint itself performs the write unconditionally once called; it
does not re-enforce confirmation server-side, that's a frontend-owned gate.

```
TicketInput.source_issue_key                    app/analysis/schemas.py
  — set by JiraImportFlow.tsx's "Use This Ticket" (= the selected issue's
    key), None for manually-entered tickets. Threaded through
    CoachingSessionState.ticket unchanged (no coaching/state.py change
    needed - the field just rides along inside TicketInput).
        ↓
FinalRequirementView.tsx reads ticket.source_issue_key
  — the "Approve & Update Jira" card renders only when this is present
    (CLAUDE.md/requirement: manually-entered tickets keep working, with no
    Jira UI at all)
        ↓
[user clicks Approve & Update Jira, then confirms]
        ↓
useUpdateJiraIssue() -> updateJiraIssue(issueKey, finalRequirement)  frontend/src/lib/api/jira.ts
        ↓
POST /api/jira/issues/{issue_key}/update  {user_story, acceptance_criteria,
                                            scope, assumptions, dependencies}
                                            app/jira/router.py
        ↓
client.update_issue(issue_key, final_requirement)   app/jira/client.py
  — description only: builds {"fields": {"description": <ADF>}} and PUTs
    it. Never includes any other field (no custom fields, assignee,
    priority, status, story points - CLAUDE.md/requirement).
        ↓
parsing.format_final_requirement_text(final_requirement)  app/jira/parsing.py
  — plain text: "User Story:\n\n...\n\nAcceptance Criteria:\n\n- ...\n\n..."
    for all five sections (user story, acceptance criteria, scope,
    assumptions, dependencies) - the full requirement, not a summary
        ↓
parsing.plain_text_to_adf(text)                    app/jira/parsing.py
  — the inverse of adf_to_plain_text(): blank-line-separated blocks each
    become one ADF node - an all-"- "-prefixed block becomes a bulletList,
    anything else becomes one paragraph per line. Minimal by design, not a
    general Markdown-to-ADF converter.
        ↓
PUT https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/issue/{issue_key}
  {"fields": {"description": <ADF doc>}}             client.py::_put()
  — 204/200 on success, no body expected; JiraAPIError on failure -> 502
        ↓
Frontend success state: confirmation text naming the updated issue, and a
"Back to Issue List" button (calls the onBackToJira callback threaded
CoachingPage -> ReviewTicketPage, which resets straight back into the Jira
import flow rather than the manual-entry screen - see the callback-driven
reset in ReviewTicketPage.tsx's handleReset(nextSource))
```

`FinalRequirementContent` (`app/coaching/schemas.py`) is reused as-is for
the update request body - `app/jira/client.py` and `app/jira/parsing.py`
import it directly from `app.coaching.schemas` rather than duplicating an
equivalent shape in `app/jira/schemas.py`. This introduces a new `jira ->
coaching` import direction that didn't exist before this change; it's a
one-way "sink" dependency (`coaching/` still imports nothing from
`jira/`), not a cycle.

**Scope change: `write:jira-work` added.** `settings.jira_scopes` is now
`"read:jira-work write:jira-work offline_access"` (§9) - a direct reversal
of the previous slice's explicit least-privilege exclusion of write
access. **Any connection made before this change is read-only and will be
rejected by Jira on an update attempt; the user must reconnect (re-run the
`/jira/authorize` flow) to get a token with the new scope** - there is no
in-app detection or prompt for this yet (see "Not yet done" below).

### Not yet done, by design

- No real `project_id` wired into RAG (§11) - `app/jira/` and
  `app/agent/rag_integration.py`'s `TEMP_EVAL_PROJECT_ID` are still
  unconnected; a real Jira project selection does not yet replace the
  temporary RAG scope.
- No persistence or multi-user auth for the Jira connection (§8) -
  single process-local connection, lost on restart.
- No dependency **inference** beyond what Jira already reports explicitly
  as a link/parent/subtask - CLAUDE.md §13's "possible dependency" LLM
  inference from ticket text is unchanged and untouched by this module.
- No detection of a stale (read-only) connection after the `write:jira-work`
  scope change - an update attempt with an old token surfaces as a normal
  `502` from Jira, not a specific "please reconnect" message.
- No Jira fields beyond `description` are ever written - no custom fields,
  assignee, priority, status transitions, or story points, and no plan to
  add them without a specific requirement (CLAUDE.md §17/§24 don't call for
  more than this).

### Tests: `tests/test_jira.py`

Pure logic (`adf_to_plain_text`, `extract_related_issues`,
`format_final_requirement_text`, `plain_text_to_adf`, the in-memory
store's state-transition rules) is tested directly with hand-built
fixtures, no network calls - same convention as
`select_weakest_criterion`/`should_stop_coaching`. Real Atlassian/Jira
HTTP calls cannot follow the project's "hit the real API, no mocking"
convention (a live OAuth consent step needs a human in a browser and
cannot run headlessly in CI), so `httpx.get`/`httpx.post` are monkeypatched
at the module level instead - consistent with how the rest of the codebase
already monkeypatches module-level functions directly rather than
introducing a mocking library dependency. Endpoint tests use `TestClient`
the same way `tests/test_coaching.py` does. The `related_issues` prompt-
wiring tests mirror `tests/test_rag_integration.py`'s
`build_user_prompt()` coverage.

## 13. Reviewed-ticket history and frontend session persistence

Two small, targeted fixes for real end-to-end testing gaps, both reusing
the existing in-memory-store/`sessionStorage` patterns rather than
introducing any real persistence:

**Reviewed-ticket history moved from frontend `useState` to a backend
in-memory store.** Previously `AppShell.tsx` held `reviewedTickets` in
React state, passed down to `DashboardPage`/`HistoryPage`/`ReviewTicketPage`
as props - lost on every page refresh. Now:

```
ReviewTicketPage.tsx (after analysis)          CoachingPage.tsx (after finalize)
        ↓                                              ↓
useRecordReviewedTicket()  →  POST /api/tickets/reviewed  →  store.upsert_reviewed_ticket()
                                                               app/tickets/store.py

DashboardPage.tsx / HistoryPage.tsx (on mount)
        ↓
useReviewedTickets()  →  GET /api/tickets/reviewed  →  store.list_reviewed_tickets()
```

`app/tickets/store.py` persists to a local SQLite file (`DB_PATH`, default
`data/tickets.db`, gitignored) via the stdlib `sqlite3` module — a single
`reviewed_tickets` table, one row per ticket, upserted by deleting any
existing row with the same `issue_key` before inserting (mirroring
`app/jira/store.py`'s upsert-by-key idea, but persisted rather than
process-local). `init_db()` creates the table if missing and is called
from a `startup` event in `app/main.py`, so a fresh `data/tickets.db` is
safe to create on every boot. Unlike the coaching/Jira-connection stores,
this survives a backend restart, not just a frontend page refresh. Still
no auth/user system to scope rows by, and still not safe for concurrent
writes from multiple worker processes.
`AppShell.tsx` no longer holds or threads `reviewedTickets`/
`onTicketReviewed` at all - `ReviewTicketPage`/`CoachingPage` each call
`useRecordReviewedTicket()` directly, and `DashboardPage`/`HistoryPage`
each call `useReviewedTickets()` directly, rather than receiving the list
as a prop from a parent that no longer holds it.

`frontend/src/lib/api/tickets.ts` keeps a private `ReviewedTicketWire`
(snake_case) interface mirroring `app/tickets/schemas.py::ReviewedTicket`
byte-for-byte, converting to/from the app's existing camelCase
`ReviewedTicket` type (`frontend/src/lib/types/reviewedTicket.ts`, used
untouched by `ReviewedTicketsTable.tsx`) at the API boundary - the same
snake_case-wire-to-camelCase-app-state transform pattern already used by
`useSubmitCoachingAnswer.ts`.

**Login/nav state moved from plain `useState` to `sessionStorage`-backed
state.** `AppShell.tsx`'s `isLoggedIn` and `activeScreen` used to reset on
any full page reload - including the reload Jira's OAuth redirect causes
when it lands back on the app after consent (`GET /jira/callback` responds
with a `302` to `settings.frontend_url`, a real top-level navigation, not a
fetch - see §12). That reload was silently bouncing a connected user back
to the login screen. Both values are now read from `sessionStorage` on
initial `useState`, and written back via a `useEffect` on every change:

```ts
const [isLoggedIn, setIsLoggedIn] = useState(readStoredIsLoggedIn);
const [activeScreen, setActiveScreen] = useState<Screen>(readStoredScreen);
useEffect(() => sessionStorage.setItem(IS_LOGGED_IN_KEY, String(isLoggedIn)), [isLoggedIn]);
useEffect(() => sessionStorage.setItem(ACTIVE_SCREEN_KEY, activeScreen), [activeScreen]);
```

This is still not real authentication (CLAUDE.md §29/out-of-scope for this
fix) - it only makes the existing cosmetic login state survive a same-tab
reload it previously didn't. `sessionStorage` (not `localStorage`) is used
deliberately: it clears when the tab closes, matching the "prototype demo,
no real auth" framing already on `LoginPage.tsx`.

### Tests: `tests/test_tickets.py`

An `autouse` fixture points `store.DB_PATH` at a fresh file under
pytest's per-test `tmp_path` and calls `store.init_db()` before every
test (`monkeypatch` restores `DB_PATH` afterward), so tests never touch
the real `data/tickets.db` and don't leak state between tests. Pure store
functions (`upsert_reviewed_ticket`, `list_reviewed_tickets`) are tested
directly with no HTTP involved, and endpoint tests use `TestClient` the
same way `tests/test_jira.py`/`tests/test_coaching.py` do.
