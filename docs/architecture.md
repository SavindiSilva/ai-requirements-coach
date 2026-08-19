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
   app/agent/graph.py (LangGraph, single-node)
        ↓
   app/agent/llm.py → Anthropic Claude API


   app/rag/  (standalone, not called by anything above yet)
        ↓
   chunking.py → embeddings.py → Anthropic-independent
                 (OpenAI API)     ChromaDB (local, persistent)
```

Coaching state is held in a process-local Python dict
(`app/coaching/store.py`) — it does not survive a process restart and is not
shared across worker processes. There is no database connection anywhere in
the codebase.

`app/rag/` is a separate, self-contained subsystem: it has its own external
dependency (OpenAI embeddings) and its own persistent store (ChromaDB on
disk), but nothing in `analysis/`, `coaching/`, or `agent/` calls into it
yet, and it exposes no HTTP endpoint. See §11.

## 2. Current backend module structure

```
app/
├── main.py            FastAPI app, CORS, router wiring, /health
├── agent/              LangGraph orchestration + Claude client (shared)
│   ├── graph.py         single-node analysis graph
│   ├── llm.py            Anthropic client wrapper, forced tool-use
│   ├── prompts.py        analysis system/user prompt templates
│   └── state.py          AgentState TypedDict
├── analysis/           Phase 1: requirement analysis
│   ├── router.py         POST /api/analyse
│   └── schemas.py        TicketInput, AnalysisContent, AnalysisResult, ...
├── coaching/            Phase 2: multi-turn clarification loop
│   ├── router.py         /api/coaching/* endpoints
│   ├── schemas.py         request/response models
│   ├── state.py           CoachingSessionState TypedDict
│   ├── store.py           in-memory session store (dict), validation errors
│   ├── selection.py       deterministic weakest-criterion selection
│   ├── stop_condition.py  deterministic stop-condition + remaining-gaps logic
│   ├── llm.py             Claude wrappers for question/finalize generation
│   └── prompts.py         coaching prompt templates
├── core/
│   └── config.py         pydantic-settings Settings (env-driven)
├── rag/                 Phase 3: standalone project-scoped RAG module
│   ├── schemas.py         DocumentType, DocumentInput, ChunkMetadata, IngestResult, RetrievedChunk
│   ├── chunking.py         pure word-based chunk_text()
│   ├── embeddings.py       OpenAI embedding client wrapper, EmbeddingError
│   └── store.py            ChromaDB PersistentClient, add_document(), retrieve(), RAGStoreError
├── auth/                empty (__init__.py only) — not started
├── database/            empty (__init__.py only) — not started
├── jira/                empty (__init__.py only) — not started
└── tickets/             empty (__init__.py only) — not started

tests/
├── test_analysis.py     Phase 1 endpoint tests (real Claude API, no mocks)
├── test_coaching.py     Phase 2 endpoint + pure-logic tests
└── test_rag.py           Phase 3 RAG tests (real OpenAI embeddings where needed, no mocks)
```

`auth/`, `database/`, `jira/`, and `tickets/` exist only as empty package
stubs (`__init__.py` with zero content). No code has been written in any of
them. `rag/` is implemented as a standalone module (see §11) but is not
called from anywhere else in the codebase yet - `analysis/` and `coaching/`
are unchanged.

## 3. Analysis flow (Phase 1)

Entry point: `POST /api/analyse` (`app/analysis/router.py`).

```
TicketInput {title, description}
        ↓
analyze_ticket()                       app/agent/graph.py
        ↓
LangGraph: START → analyze_requirement_node → END
        ↓
build_system_prompt() + build_user_prompt()   app/agent/prompts.py
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
or not coaching history is supplied.

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
    → generate_final_requirement()      Claude call, forced tool-use
                                          (idempotent — cached on session after first call)
    ← {final_requirement, remaining_gaps, current_scores, ...}
```

Notes on what is **not** implemented in this flow:
- No user-approval endpoint (`POST /api/requirements/{id}/approve` from
  CLAUDE.md §24 does not exist).
- No Jira update step — finalize only returns the structured requirement;
  nothing writes it anywhere.
- The router docstring in `app/coaching/router.py` explicitly labels its
  steps "Phase 2A" through "Phase 2E", which matches this incremental build
  history.

## 5. LangGraph usage

Only one graph exists, and it is intentionally minimal:

```python
# app/agent/graph.py
START → analyze_requirement_node → END
```

A single-node graph. There is no multi-node coaching graph — the "wait for
user / re-evaluate / more gaps?" loop described conceptually in CLAUDE.md
§11 is implemented as plain FastAPI request/response endpoints in
`app/coaching/router.py` calling ordinary Python functions, **not** as
LangGraph nodes/edges. `AgentState` (`app/agent/state.py`) is a `TypedDict`
with `ticket`, `analysis`, and `coaching_history` — it is reused by the
single analysis node regardless of whether the call originates from
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

Endpoints listed in CLAUDE.md §24 that **do not exist yet**: `GET
/api/coaching/{session_id}`, `POST /api/requirements/{id}/approve`, and all
`GET /api/jira/...` endpoints. `app/main.py` has commented-out placeholder
imports for a `jira_router` and `tickets_router` that are not yet built.

## 8. Current state/persistence approach

- **No database.** `app/database/` is an empty stub; no SQLAlchemy models,
  no Supabase client usage, no connection pooling anywhere in the code.
- **Coaching sessions**: a single process-local `dict[str,
  CoachingSessionState]` in `app/coaching/store.py` (`_SESSIONS`). Explicitly
  documented in that module's docstring as a temporary placeholder — "does
  not survive process restarts and is not safe across multiple worker
  processes" — pending real DB-backed persistence.
- **Analysis results** (Phase 1, standalone `/api/analyse` calls): not
  persisted at all — returned directly in the HTTP response and discarded.
- **No auth**: `app/auth/` is an empty stub; there is no session/user
  concept, so coaching sessions are not scoped to any user.

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
| `jira_client_id`, `jira_client_secret`, `jira_redirect_uri`, `jira_scopes` | No | Declared, unused — no Jira code exists yet |
| `max_clarification_rounds` | Yes | Used by `stop_condition.py` and the analysis system prompt (caps question count) |
| `readiness_pass_threshold` | Yes | Used by `stop_condition.py` (per-criterion stop bar, not `overall_readiness`) |

**External services actually called at runtime today:** the Anthropic
Claude API (analysis + coaching) and, as of Phase 3, the OpenAI embeddings
API and a local persistent ChromaDB instance (both only from within
`app/rag/`, not yet from the analysis/coaching pipeline). Supabase/Postgres
and Jira are still configured but not yet integrated or called anywhere.

CORS is configured with a single allowed origin (`settings.frontend_url`),
all methods and headers, credentials allowed.

## 10. Current implementation status

| Area | Status | Evidence |
|---|---|---|
| Core AI analysis | **Implemented** | `app/analysis/`, `app/agent/`, `POST /api/analyse`, `tests/test_analysis.py` |
| Readiness scoring | **Implemented** | 4-criterion scoring + Python-computed `overall_readiness` in `app/agent/graph.py`; deterministic stop/gap logic in `app/coaching/stop_condition.py` |
| Coaching | **Implemented** | Full start → message → reanalyze → next → finalize loop in `app/coaching/`, covered by `tests/test_coaching.py` |
| Frontend integration | **Not implemented** | No frontend code found in this repository |
| Jira integration | **Not implemented** | `app/jira/` is an empty stub; no OAuth, no REST client, no routes |
| RAG | **Implemented** (standalone module, not yet integrated) | `app/rag/`, `tests/test_rag.py` — ingestion, embedding, ChromaDB storage/retrieval with `project_id` filtering all implemented and tested; not yet wired into analysis/coaching prompts, no API router, no `project_id` on tickets/sessions. See §11. |
| Jira update | **Not implemented** | Depends on Jira integration, which does not exist; no approval endpoint exists either |
| Deployment | **Not implemented** | No Dockerfile, no CI config, no Render/Vercel deployment config found in the repository |

Everything under `analysis/`, `coaching/`, and `rag/` is complete and
tested for its currently defined scope. RAG's scope is deliberately
narrower than the other two (standalone module only, not yet integrated
into the product workflow) — that narrower scope is itself fully
implemented, not partially built. Everything else (`auth/`, `database/`,
`jira/`, `tickets/`) is an untouched empty stub.

## 11. RAG module (Phase 3, standalone)

`app/rag/` is a self-contained subsystem for project-scoped document
ingestion and semantic retrieval. It is not called from `analysis/`,
`coaching/`, or `agent/`, and has no API router — see CLAUDE.md §20 and the
Phase 3 task constraints for why prompt integration is deliberately
deferred.

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
- No document-management layer exists (no update/delete, no listing) —
  only `add_document()` (create) and `retrieve()` (query), matching the
  "do not build a complicated document management system" constraint.
- Not yet built, intentionally: an API router, prompt-integration into
  `analysis/`/`coaching/`, and a `project_id` concept on `TicketInput` or
  `CoachingSessionState` (nothing upstream currently produces a
  `project_id` to pass in).

Tests (`tests/test_rag.py`) split into two groups: pure/deterministic
tests that always run (chunking, input validation, and one deliberate
invalid-API-key call that exercises `EmbeddingError` against the real
OpenAI API), and embedding-dependent end-to-end tests (ingest → retrieve,
cross-project isolation, metadata preservation) that are skipped when
`OPENAI_API_KEY` is not configured locally — mirroring how
`test_analysis.py`/`test_coaching.py` depend on a locally-configured
`ANTHROPIC_API_KEY`.
