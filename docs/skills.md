# Technical Patterns — Current State

> This document captures conventions that are **already established** in the
> codebase, so future work follows the same style instead of introducing
> parallel patterns. It now includes RAG (Phase 3, standalone module — see
> §8), added once implemented rather than planned in advance. It still does
> **not** cover Jira, auth, or database patterns — none of those have been
> implemented yet, so there is nothing real to document for them.

## 1. Claude structured-output pattern

Every Claude call in the codebase follows the same shape, established in
`app/agent/llm.py` and reused as-is in `app/coaching/llm.py`. Do not
introduce a different structured-output mechanism (e.g. JSON-mode prompting,
free-text parsing) without a strong reason.

1. Define the expected output as a Pydantic model.
2. Build a single tool dict whose `input_schema` is that model's
   `model_json_schema()`:
   ```python
   _MY_TOOL = {
       "name": "submit_x",
       "description": "...",
       "input_schema": MyModel.model_json_schema(),
   }
   ```
3. Call `client.messages.create(...)` with `tools=[_MY_TOOL]` and
   `tool_choice={"type": "tool", "name": "submit_x"}` — this forces Claude to
   call exactly that tool, so there is never a plain-text response to parse.
4. Scan `response.content` for the `tool_use` block matching that tool name,
   then re-validate its `.input` through the same Pydantic model:
   ```python
   for block in response.content:
       if block.type == "tool_use" and block.name == "submit_x":
           return MyModel.model_validate(block.input)
   ```
5. If no matching `tool_use` block is found, or validation fails, raise a
   module-specific error (see §5) — never fall back to guessing or returning
   partial data.

The Claude client itself is a single lazily-instantiated, module-level
singleton (`app/agent/llm.py::get_client()`), reused everywhere via import
rather than each module creating its own client.

## 2. Pydantic validation pattern

- All request/response shapes and internal data are Pydantic `BaseModel`s —
  no raw dicts cross a function boundary that represents ticket, analysis,
  or coaching data.
- Field-level constraints are declared inline with `Field(...)`
  (`min_length=1`, `ge=0, le=3`, etc.) rather than validated manually in
  route bodies.
- Custom validation beyond what `Field` expresses uses `@field_validator`
  (see `MessageRequest.answer_must_not_be_blank` in
  `app/coaching/schemas.py`), not ad-hoc `if` checks in the router.
- A derived/computed value that must never be trusted from the LLM is
  **not** part of the schema Claude fills in. Example: `AnalysisContent`
  (what Claude produces via forced tool-use) deliberately excludes
  `overall_readiness`; `AnalysisResult` (the API response model) extends
  `AnalysisContent` by adding `overall_readiness`, which is computed in
  plain Python (`_compute_overall_readiness` in `app/agent/graph.py`) after
  the LLM call returns. This split-model pattern is how the codebase keeps
  "LLM-authored" fields separate from "code-computed" fields.
- LLM output is always re-validated through the same Pydantic model it was
  requested against (`Model.model_validate(tool_use.input)`), even though
  the schema was already given to Claude as the tool's `input_schema` — the
  schema constrains generation but is never treated as a substitute for
  validating the actual response.

## 3. LangGraph usage

- One `StateGraph` per distinct workflow, built by a `build_graph()`
  function and compiled once, memoized behind a `get_graph()` accessor using
  a module-level `_compiled_graph` global — avoids recompiling the graph on
  every request.
- Graph state is a `TypedDict` (see `app/agent/state.py::AgentState`), not a
  Pydantic model — LangGraph nodes read/return plain dict-shaped state.
- Nodes are plain functions of `(state) -> state` (partial dict updates are
  fine; see `analyze_requirement_node`). Node functions do not call the
  Claude API directly — they delegate to a separate `llm.py` module function
  and a separate `prompts.py` module for prompt construction. Keep that
  three-way split (node orchestration / prompt building / LLM call) rather
  than inlining prompt strings or API calls into the node function.
- **Only use LangGraph for genuinely multi-node/stateful orchestration.**
  The existing analysis graph is a single node (`START →
  analyze_requirement_node → END`) because that's genuinely all Phase 1
  needs. The multi-step coaching loop (start/answer/reanalyze/next/finalize)
  is **not** implemented as LangGraph nodes — it's plain FastAPI endpoints
  calling ordinary functions, because each step is a separate HTTP
  round-trip driven by the user, not an in-process loop. Don't force
  something into a LangGraph node just because it's "part of the agent" —
  match the tool to whether the step is an internal transition or an
  external request/response boundary.

## 4. FastAPI route conventions

- One `APIRouter()` per module (`app/analysis/router.py`,
  `app/coaching/router.py`), included into `app/main.py` with an `/api`
  prefix and a tag matching the module name. Routers are imported and
  included one at a time, directly in `main.py` (not auto-discovered) —
  new modules add their own `from app.x.router import router as x_router` +
  `app.include_router(...)` lines there.
- Route functions are thin: parse/validate input via the Pydantic request
  model (FastAPI does this automatically from the type annotation), delegate
  to plain functions from other modules (graph invocation, store functions,
  selection/stop-condition logic), and shape the typed `response_model`.
  Business logic does not live in the route body.
- Every route declares an explicit `response_model=...`.
- Path parameters that identify a resource (e.g. `session_id`) are plain
  strings passed straight to the relevant store lookup function — no
  dependency-injection-based resource loading is used yet.

## 5. Error-handling conventions

- Each module that can fail defines its own narrow exception type(s) as
  plain `Exception`/`RuntimeError` subclasses close to where the failure
  originates:
  - `app/agent/llm.py::LLMAnalysisError`
  - `app/coaching/llm.py::CoachingLLMError`
  - `app/coaching/store.py`: several precise state-machine errors
    (`SessionNotFoundError`, `NoUnansweredQuestionError`,
    `NoAnsweredQuestionsError`, `InconsistentHistoryError`,
    `CoachingAlreadyCompleteError`, `PendingQuestionError`,
    `CoachingNotCompleteError`) — one exception type per distinct invalid
    state transition, not one generic "bad state" error.
- Routes catch these specific exception types and translate them to HTTP
  errors via `raise HTTPException(status_code=..., detail=str(exc)) from
  exc` — never a bare `except Exception` at the route level, and never an
  unhandled exception left to become a generic 500.
- Status code convention observed: external/LLM failures →
  `502`; invalid client-driven state transitions (e.g. answering a
  nonexistent session, finalizing before coaching is complete) → `400`;
  missing resource (unknown `session_id`) → `404`.
- Inside a module function, a failing external call is wrapped in
  `try/except Exception as exc: raise <SpecificError>(f"...: {exc}") from
  exc` — the original exception is preserved via `from exc`, and the message
  is rewrapped into the module's own error vocabulary rather than leaking
  the raw underlying exception type to callers.
- Store functions validate state and raise *before* mutating anything
  (documented explicitly in several docstrings, e.g. "Raises without
  mutating state if..." in `app/coaching/store.py`) — validate-then-mutate,
  not partial mutation followed by rollback.

## 6. Testing conventions

- Tests hit the **real Claude API directly through the FastAPI
  `TestClient`** — no mocking of the Anthropic client anywhere in the test
  suite. This is an explicit, stated convention (see the docstring at the
  top of `tests/test_analysis.py` and `tests/test_coaching.py`), not an
  oversight. `ANTHROPIC_API_KEY` is expected to be configured locally for
  tests to run.
- Deterministic, LLM-free logic (`select_weakest_criterion`,
  `should_stop_coaching`, `compute_remaining_gaps`) is tested directly
  against hand-constructed model instances (e.g. a local
  `_make_analysis(rc, ac, oq, sd)` helper), with **no API call and no
  TestClient**, specifically so this logic can be exercised cheaply and
  deterministically. This mirrors those modules' own design goal, stated in
  their docstrings, of being "pure and LLM-free by design ... so it can be
  unit tested directly."
- Where a full endpoint test needs a session in a specific state, tests
  build that state directly via the store function (e.g.
  `app.coaching.store.create_session`) instead of always driving the full
  multi-step HTTP flow — full start-to-finish flow tests are reserved for
  where the spec specifically calls for testing that flow.
- Response shape assertions are structural (loop over a tuple of expected
  field names, assert type/range) rather than asserting exact LLM-authored
  string content — appropriate given responses are genuinely
  non-deterministic across real API calls.
- Test tickets are named constants at module level (`VAGUE_TICKET`,
  `CLEAR_TICKET`) reused across test functions, not redefined inline per
  test.

## 7. Configuration/secrets conventions

- All configuration goes through one `pydantic_settings.BaseSettings`
  subclass: `app/core/config.py::Settings`, instantiated once as a
  module-level singleton `settings = Settings()`, imported wherever needed
  (`from app.core.config import settings`) — never `os.environ` accessed
  directly outside this file.
- `model_config = SettingsConfigDict(env_file=".env", extra="ignore")` — env
  vars are loaded from a local `.env` file (gitignored) in development;
  `extra="ignore"` means unrecognized env vars don't raise.
- Every setting has a typed default (usually `""` for secrets, a real
  default for tunables like `max_clarification_rounds: int = 5`) — the
  class never raises just from being imported, even with no `.env` present.
- `.env.example` is kept in sync with `Settings` fields as living
  documentation of what's configurable, with comments pointing to where to
  obtain each credential — every field in `Settings` has a corresponding
  (empty) entry in `.env.example`.
- Secrets (`anthropic_api_key`, future `openai_api_key`,
  `jira_client_secret`, `supabase_secret_key`) are declared only in
  `Settings`/`.env`/`.env.example` — grep confirms no hardcoded key-like
  strings exist in `app/`.
- Tunable business values that affect behavior (not just external service
  config) also live in `Settings`, not as inline constants — e.g.
  `max_clarification_rounds` and `readiness_pass_threshold` are read from
  `settings` at the point of use in `app/coaching/stop_condition.py` and
  `app/agent/prompts.py`, rather than hardcoded in that logic.
- Counter-example, by design: `app/rag/chunking.py`'s `chunk_size`/
  `chunk_overlap` and `app/rag/store.py`'s default retrieval `k` are plain
  function-parameter defaults, not `Settings` fields — they're tuning knobs
  for a single function call, not deployment-environment configuration, so
  adding them to `Settings` would be an unnecessary abstraction for what
  they actually are.

## 8. RAG module patterns (Phase 3)

See `docs/architecture.md` §11 for the full ingestion/retrieval flow. This
section covers only the patterns worth reusing elsewhere, to avoid
duplicating that flow description here.

- **Second external-service client, same singleton shape.** `app/rag/
  embeddings.py::get_embedding_client()` is a lazily-instantiated,
  module-level `OpenAI` client singleton, structurally identical to
  `app/agent/llm.py::get_client()`'s `Anthropic` singleton. When adding a
  new external API client anywhere in the codebase, follow this exact
  shape rather than instantiating a client per-call or per-request.
- **A second typed-error-per-module pair**, extending the convention in §5:
  `EmbeddingError` (`app/rag/embeddings.py`) for OpenAI call failures, and
  `RAGStoreError` (`app/rag/store.py`) for ChromaDB read/write failures —
  kept separate because they fail independently and a caller may want to
  handle "embedding is down" differently from "the vector store is down."
  Plain `ValueError` is used instead for caller-input mistakes that aren't
  external-service failures (e.g. an empty `project_id`, an empty texts
  list) — mirrors how `MessageRequest`'s field validator distinguishes a
  bad request from a downstream failure, just via a plain exception instead
  of Pydantic since there is no request schema for these standalone
  functions yet.
- **A safety invariant enforced in code, not just by convention.**
  `retrieve()` requires and applies `project_id` as a ChromaDB metadata
  `where` filter unconditionally — cross-project isolation is not something
  a caller can accidentally skip by forgetting a parameter, because there
  is no code path that queries without it. When a correctness requirement
  is this important (see CLAUDE.md §18-19), enforce it inside the function
  that owns the invariant rather than trusting every call site to apply it.
- **Chunking is a pure function** (`app/rag/chunking.py::chunk_text`) with
  no I/O and no dependency on `Settings` or any client — same "pure and
  side-effect free by design" pattern as `app/coaching/selection.py` and
  `app/coaching/stop_condition.py`, and for the same reason: it's the part
  of the pipeline that's cheapest to get exhaustively right with plain unit
  tests, so keep it free of anything that would force those tests to hit a
  network call.
- **No LangChain document-loader/text-splitter abstractions** were
  introduced for chunking or the ChromaDB interaction, even though
  `langchain-openai` and `langchain` are already dependencies (used for
  LangGraph) — `chunk_text()` is a ~30-line pure function and
  `app/rag/store.py` calls the `chromadb` client directly. Reach for a
  framework abstraction only when the plain-Python version has become
  genuinely hard to maintain, not by default.
- **Testing an error path without mocking the API.** To test
  `EmbeddingError` deterministically regardless of whether a valid
  `OPENAI_API_KEY` happens to be configured locally, the test
  (`tests/test_rag.py::test_embed_texts_raises_embedding_error_on_invalid_api_key`)
  monkeypatches the module-level client singleton to one constructed with
  an intentionally invalid key, then makes a real call against it. This
  still exercises the real API and the real failure path (no response is
  faked) — it stays consistent with the "hit the real API, no mocking"
  convention in §6 while still being deterministic.
- **Tests that need a real embedding are skipped, not faked, when
  `OPENAI_API_KEY` isn't configured locally** (`pytest.mark.skipif`) — this
  extends the existing convention (§6) of tests depending on a real,
  locally-configured API key rather than mocking the client, applied to a
  second external service.
