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
├── auth/                empty (__init__.py only) — not started
├── database/            empty (__init__.py only) — not started
├── jira/                empty (__init__.py only) — not started
└── tickets/             empty (__init__.py only) — not started

tests/
├── test_analysis.py       Phase 1 endpoint tests (real Claude API, no mocks) — unchanged
├── test_coaching.py       Phase 2 endpoint + pure-logic tests — unchanged
├── test_rag.py             Phase 3 standalone RAG tests — unchanged
└── test_rag_integration.py Phase 3 prompt-integration tests: deterministic prompt-construction
                             and fail-safe-retrieval tests, plus one real-Claude-call regression test

scripts/
└── rag_eval.py           manual, non-CI with-RAG vs. without-RAG comparison (not part of pytest)
```

`auth/`, `database/`, `jira/`, and `tickets/` exist only as empty package
stubs (`__init__.py` with zero content). No code has been written in any of
them. `rag/` itself (chunking/embeddings/store/schemas) was not modified in
this pass — the integration lives entirely in the new
`app/agent/rag_integration.py`, plus small additive changes to
`app/agent/graph.py`, `app/agent/prompts.py`, `app/coaching/prompts.py`,
and `app/coaching/router.py` (see §3, §4, §11).

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
Claude API (analysis + coaching) and the OpenAI embeddings API + a local
persistent ChromaDB instance — the latter two now called from the
analysis/coaching pipeline itself (via `app/agent/rag_integration.py`), not
only from within `app/rag/`. Every one of those calls fails safe: if
`OPENAI_API_KEY` is unset or the call fails, analysis/coaching proceed with
no RAG context rather than erroring. Supabase/Postgres and Jira are still
configured but not yet integrated or called anywhere.

CORS is configured with a single allowed origin (`settings.frontend_url`),
all methods and headers, credentials allowed.

## 10. Current implementation status

| Area | Status | Evidence |
|---|---|---|
| Core AI analysis | **Implemented** | `app/analysis/`, `app/agent/`, `POST /api/analyse`, `tests/test_analysis.py` |
| Readiness scoring | **Implemented** | 4-criterion scoring + Python-computed `overall_readiness` in `app/agent/graph.py`; deterministic stop/gap logic in `app/coaching/stop_condition.py` |
| Coaching | **Implemented** | Full start → message → reanalyze → next → finalize loop in `app/coaching/`, covered by `tests/test_coaching.py` |
| Frontend integration | **Partially implemented** | `frontend/` (React + Vite): `POST /api/analyse`, and the full coaching loop (`/start`, `/message`, `/reanalyze`, `/next`, `/finalize`) are wired to real backend calls under `frontend/src/lib/api/` and `frontend/src/hooks/`. No Jira UI, no approval/update flow, no persistence across page refresh (coaching state is React-in-memory only). |
| Jira integration | **Not implemented** | `app/jira/` is an empty stub; no OAuth, no REST client, no routes |
| RAG | **Implemented** — standalone module + evaluation-scoped prompt integration | `app/rag/`, `app/agent/rag_integration.py`, `tests/test_rag.py`, `tests/test_rag_integration.py` — ingestion, embedding, retrieval, and now analysis/coaching-finalize prompt integration are all implemented and tested. Uses a **temporary hardcoded `project_id="default"`** (see §11) — no API router, no real `project_id` on tickets/sessions, no Jira/frontend project context yet. |
| Jira update | **Not implemented** | Depends on Jira integration, which does not exist; no approval endpoint exists either |
| Deployment | **Not implemented** | No Dockerfile, no CI config, no Render/Vercel deployment config found in the repository |

Everything under `analysis/`, `coaching/`, and `rag/` (including its
`app/agent/rag_integration.py` glue) is complete and tested for its
currently defined scope. RAG's scope is deliberately narrower than the
other two in one specific way: it evaluates against a single, explicitly
temporary `project_id="default"` rather than real per-project context —
that narrower scope is itself fully implemented, not partially built.
Everything else (`auth/`, `database/`, `jira/`, `tickets/`) is an untouched
empty stub.

## 11. RAG module (Phase 3: standalone module + evaluation-scoped prompt integration)

`app/rag/` is a self-contained subsystem for project-scoped document
ingestion and semantic retrieval — unchanged from its first Phase 3 pass
(see the ingestion/retrieval diagrams below). It still has no API router.
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
- No document-management layer exists (no update/delete, no listing) —
  only `add_document()` (create) and `retrieve()` (query), matching the
  "do not build a complicated document management system" constraint.
- Not yet built, intentionally: an API router, and a real `project_id`
  concept on `TicketInput` or `CoachingSessionState` (nothing upstream
  currently produces a real one to pass in).

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
