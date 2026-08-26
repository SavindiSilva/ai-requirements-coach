# Technical Patterns — Current State

> This document captures conventions that are **already established** in the
> codebase, so future work follows the same style instead of introducing
> parallel patterns. It now includes RAG (Phase 3: the standalone module in
> §8, and its prompt integration into analysis/coaching in §9) and, within
> §9, how Jira's `related_issues` wiring followed that same pattern. The
> Jira module's own patterns (OAuth 2.0 3LO, in-memory token storage, a
> dynamic-credential HTTP client) are implemented in `app/jira/` and
> described in `docs/architecture.md` §12, but are not yet written up here
> as reusable conventions. Real (frontend-only) authentication now exists
> via Supabase Auth — see `docs/architecture.md` §14 for the flow and §10
> below for the one pattern it touches; there is still no *backend* auth
> pattern to document, since `app/auth/` remains an empty stub. This
> document still does **not** cover database patterns — no SQLAlchemy/
> Supabase-Postgres code has been written yet, so there is nothing real to
> document for that.

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
   partial data. One narrow, explicitly-named exception exists (§12): a
   fixed, small set of *recoverable* malformed shapes may be coerced before
   validation, logged when it fires — this is not "guessing" at content, it
   only reshapes content Claude already produced.

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
  The analysis graph started as a single node and, in Phase 3, grew to two
  (`START → retrieve_context_node → analyze_requirement_node → END`) when a
  genuinely internal, in-process step (RAG retrieval) was added ahead of
  it — that's the concrete example of when growing the graph is the right
  call. The multi-step coaching loop (start/answer/reanalyze/next/finalize)
  is still **not** implemented as LangGraph nodes — it's plain FastAPI
  endpoints calling ordinary functions, because each step is a separate
  HTTP round-trip driven by the user, not an in-process loop. Don't force
  something into a LangGraph node just because it's "part of the agent" —
  match the tool to whether the step is an internal transition (add a node)
  or an external request/response boundary (don't).

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

## 9. Wiring an optional external capability into an existing pipeline safely

`app/agent/rag_integration.py` is the concrete example of this pattern:
connecting RAG retrieval into the analysis/coaching prompts without being
allowed to change existing behaviour when the capability is unavailable.
Reuse this shape for the next optional external capability added to an
existing pipeline.

**Follow-through: Jira's `related_issues` reused three of these rules
directly** (see `docs/architecture.md` §12 for the full flow) — the
optional-trailing-field-on-the-existing-schema approach
(`TicketInput.related_issues: list[RelatedIssue] | None = None`, not a new
required field or a parallel schema), the
empty-input-reproduces-pre-integration-output rule
(`if ticket.related_issues:` in `build_user_prompt()`, so every pre-Jira
caller is byte-for-byte unaffected), and formatting the optional content
inline at its one call site (no separate formatter module was needed here,
since - unlike RAG chunks - there was only ever one place that needed to
render `RelatedIssue` into prompt text). It deliberately did **not** reuse
the "fail safe by construction" rule below: RAG failing degrades gracefully
to no context, but a user-initiated Jira read has no sensible
silent-failure mode, so `app/jira/router.py` surfaces real `401`/`502`
errors instead of swallowing them - a different, equally valid answer to
the same "optional capability" shape, not a departure from it.

- **One glue module, not logic duplicated at each call site.** Both call
  sites (`retrieve_context_node` in `app/agent/graph.py`,
  `finalize_coaching_session()` in `app/coaching/router.py`) call the same
  `get_retrieved_context()` rather than each re-implementing the
  short-circuit/try-except. If a second integration point needs the same
  optional capability, make it call the existing wrapper — don't copy the
  fail-safe logic inline again.
- **Fail safe by construction, not by hoping callers remember to catch.**
  `get_retrieved_context()` never raises: it returns `[]` (a) before even
  attempting a call when the prerequisite config (`settings.openai_api_key`)
  is missing, and (b) whenever the underlying call raises any of its known
  failure types. Callers (`retrieve_context_node`, `finalize_coaching_session`)
  don't need their own try/except — the guarantee lives in the one function
  that owns the integration, the same "enforce the invariant where it's
  owned" principle as §8's `project_id` filtering.
- **The empty-input case must reproduce the pre-integration output
  exactly.** `build_user_prompt()`/`build_finalize_user_prompt()` only add
  their new prompt section when the optional data is genuinely present
  (`if context_text:` / `if retrieved_context:`) — passing `None` or `[]`
  must be indistinguishable from the parameter not existing at all. This is
  what let Phase 1/2 tests keep passing unmodified: every pre-Phase-3
  caller either omits the new parameter or naturally receives `[]` from
  the fail-safe wrapper.
- **A new optional trailing parameter, not a new required one.** Both
  `build_user_prompt()` and `build_finalize_user_prompt()` added
  `retrieved_context` as the *last*, default-`None` parameter — existing
  positional and keyword call sites keep working unchanged. (One exception
  surfaced this: a test in `tests/test_coaching.py` monkeypatches
  `build_finalize_user_prompt` with its own hand-written stub function, and
  Python doesn't apply the real function's defaults to a replacement stub —
  the stub itself needed the new parameter added, with its own `=None`
  default, to keep accepting the same call. That's a test-infrastructure
  consequence of monkeypatching a whole function rather than a design
  problem with the parameter itself.)
- **Format the optional content once, centrally.** `format_context_for_prompt()`
  lives in the same glue module as the retrieval wrapper, not duplicated in
  both `app/agent/prompts.py` and `app/coaching/prompts.py` — both prompt
  builders import and call the same formatter.
- **A single, clearly-named temporary constant for scaffolding that must
  not become permanent.** `TEMP_EVAL_PROJECT_ID = "default"` lives in
  exactly one file, is never accepted from a request schema, and is
  documented at its definition and in CLAUDE.md §7 as scaffolding to be
  replaced — not extended. If a future integration needs a similar
  temporary placeholder before its real dependency exists, follow this
  shape (one named constant, one file, explicit removal plan) rather than
  hardcoding the placeholder value at each use site.

## 10. Frontend: surviving a same-tab reload without real persistence

`AppShell.tsx`'s `activeScreen` (docs/architecture.md §13) is the
reference example for making purely cosmetic frontend state survive a
page reload without adding real persistence. Reuse this shape any time a
future fix needs "must survive this tab's reload" without needing "must
survive a new tab/device/backend restart". (Login state used to follow
this same pattern via an `isLoggedIn` flag — it was later replaced with a
real Supabase Auth session, docs/architecture.md §14, which persists
itself and needs none of this. `activeScreen` still applies, since nav
position genuinely is scoped to "this tab, until it's closed.")

- Read the initial value from `sessionStorage` via the `useState`
  initializer function (`useState(readStoredScreen)`), not a bare
  literal — this reads storage exactly once, on mount, not on every
  render.
- Write back with a `useEffect` keyed on that value's own dependency array
  (`useEffect(() => sessionStorage.setItem(...), [activeScreen])`) — keep
  one effect per stored value rather than one combined effect for
  multiple values, so each write only fires when its own value actually
  changes.
- Validate whatever comes back out of storage before trusting it as the
  typed value (`readStoredScreen()` falls back to `'dashboard'` unless the
  stored string is one of the known `Screen` values) — storage can contain
  a stale value from a previous build.
- Prefer `sessionStorage` over `localStorage` when the state is explicitly
  not meant to be "real" persistence — it clears on tab close, which keeps
  the behavior honest about what it actually guarantees. (Contrast: real
  session persistence, like the Supabase Auth session in §14, should use
  whatever the auth provider's own client does by default — don't
  reimplement that with `sessionStorage`.)
- This is a plain browser API, not a new dependency or abstraction — don't
  reach for a state-management library or a backend session endpoint for
  something that's explicitly scoped to "one tab, until it's closed."

## 11. Lightweight local persistence with stdlib `sqlite3`

`app/tickets/store.py` (docs/architecture.md §13) is the reference example
for giving a single process-local store real (restart-surviving)
persistence without pulling in Postgres/Supabase/SQLAlchemy. Reach for
this shape when a store needs to survive a backend restart but doesn't
need a shared/multi-process database — CLAUDE.md §21's Postgres-via-
Supabase is still the answer for anything that does:

- Use the stdlib `sqlite3` module directly against one local file (a
  module-level `DB_PATH: Path`, gitignored) — no ORM, no new dependency.
  Open and close a connection per call (`_connect()` /
  `conn.close()` in a `try`/`finally`); don't hold one open across calls.
- Expose an `init_db()` that runs `CREATE TABLE IF NOT EXISTS` and is safe
  to call every time the app starts — call it from a `startup` event in
  `app/main.py` (`@app.on_event("startup")`), not at import time, so tests
  can point `DB_PATH` at a temp file before the table is created.
- Keep the module's existing public function signatures unchanged when
  swapping an in-memory store for this — callers (routers, other modules)
  shouldn't need to change at all.
- Tests: point `store.DB_PATH` at a fresh file under pytest's per-test
  `tmp_path` via an `autouse` fixture using `monkeypatch.setattr`, then
  call `init_db()` before each test. This isolates every test into its own
  database file and never touches the real data file, without needing
  manual cleanup (`monkeypatch` reverts `DB_PATH`, and `tmp_path` is
  cleaned up by pytest).
- This is still process-local in the sense that concurrent writes from
  multiple worker processes aren't safe — it solves "survives a restart,"
  not "safe for horizontal scaling." Document that limitation in the
  module docstring, same as the in-memory stores it replaces.

## 12. Recovering from a narrow set of malformed forced tool-use shapes

`app/coaching/llm.py::normalize_final_requirement_input()` (used by
`generate_final_requirement()`) is the reference example for when it's
correct to coerce a Claude forced-tool-use response instead of following
§1's normal "raise on any validation failure" rule. Forced `tool_choice`
guarantees *which* tool Claude calls, not that every argument's runtime
type matches the JSON Schema — under genuinely low-information input (e.g.
a ticket that reached `max_questions_reached` with consistently vague
coaching answers), Claude can occasionally collapse a list-typed field into
a plain string, or omit a required field. Reach for this pattern only when
all of the following hold — it is not a general "make validation errors go
away" tool:

- The set of malformed shapes being recovered is **small, explicitly named,
  and individually justified** — here, exactly two: a list-typed field
  returned as a non-empty string (wrapped as a single-item list, preserving
  Claude's actual text), and a missing/blank required field with an honest,
  clearly-labeled fallback synthesized from data already in hand (never
  fabricated content). Anything else is left alone for Pydantic to reject
  normally — there's nothing safe to guess there.
- The coercion function is **pure** (`dict -> dict`, no I/O besides the log
  line) so it's directly unit-testable with hand-built malformed dicts, no
  LLM call needed — same convention as `select_weakest_criterion`/
  `should_stop_coaching` (§6).
- Every time it actually fires, it **logs a warning** naming the field(s)
  coerced and enough context to find the case again (here, `session_id`) —
  `logging.getLogger(__name__)`, mirroring `app/agent/rag_integration.py`.
  The point is visibility into how often the underlying prompt-following
  issue recurs, not a silent patch-over.
- The system prompt is **also** hardened with the explicit type contract
  (list fields must always be a JSON array even with one item; the
  always-required field must always be present) as complementary
  prevention. The coercion is what actually guarantees the endpoint can't
  hard-fail on this input class; the prompt wording only reduces how often
  the coercion path is needed — it is not a substitute for it.
- To test the integration end-to-end (not just the pure coercion function),
  fake the Anthropic client itself (a minimal stand-in for
  `client.messages.create()` returning a `tool_use` block with the exact
  malformed `input` dict) and monkeypatch `app.coaching.llm.get_client` —
  this exercises the real `generate_final_requirement()`, unlike the
  existing convention of monkeypatching
  `app.coaching.router.generate_final_requirement` wholesale (which is
  right for testing router orchestration, but bypasses this function
  entirely).

## 13. Making a hardcoded value deployment-configurable without changing local dev

Two concrete examples: `app/tickets/store.py`'s SQLite `DB_PATH` and
`app/main.py`'s CORS `allow_origins`, both changed to support deploying to
Render/Vercel (docs/architecture.md §9, §10) without touching local dev
behavior. Reach for this shape any time a value needs to become
environment-configurable for a new deployment target:

- **The new `Settings` field's default must equal the value that was
  hardcoded before**, exactly — not a "sensible new default," the literal
  old value (`tickets_db_path: str = "./data/tickets.db"`, matching what
  `DB_PATH = Path("data/tickets.db")` was). This is what makes the change
  provably additive: with no new env var set, behavior is byte-for-byte
  unchanged, not just "probably fine."
- **When the old value fed a list-shaped parameter (CORS `allow_origins`),
  keep the fallback list-shaped, not empty/permissive.** `cors_allowed_origins`
  defaults to `""`; `app/main.py` parses it into a list only when non-empty,
  and falls back to `[settings.frontend_url]` — the exact single-origin
  list CORS always used — rather than defaulting to `[]` (which would
  silently block everything) or `["*"]` (which would silently become
  permissive). The fallback must reproduce prior behavior, not guess at
  new behavior.
- **Prove the default is unchanged, don't just assert it.** After making
  a value configurable, actually resolve it with no new env var set
  (`python -c "from app.core.config import settings; print(settings.x)"`,
  or import the module that derives from it) and confirm the resolved
  value matches the old hardcoded one — this is cheap and catches a typo'd
  default immediately, rather than after a deploy.
- **A module-level constant computed from `settings` at import time (not a
  direct `settings.x` reference at every call site) is fine to keep** if
  something outside the module needs to monkeypatch it — `app/tickets/store.py`
  keeps its module-level `DB_PATH = Path(settings.tickets_db_path)`
  specifically because `tests/test_tickets.py` already monkeypatches
  `store.DB_PATH` directly (§11); switching every internal reference to
  `settings.tickets_db_path` inline would have broken that test fixture
  for no benefit.
