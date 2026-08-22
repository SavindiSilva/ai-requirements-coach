# AI Requirements Coach

## 1. Project Overview

AI Requirements Coach is an AI-powered requirements refinement assistant for software teams.

The system helps users take incomplete or ambiguous software tickets and turn them into development-ready requirements before development begins.

The core workflow is:

Jira Ticket
    ↓
Requirement Analysis
    ↓
Readiness Scoring
    ↓
Identify Gaps
    ↓
Clarification Questions
    ↓
AI Coaching Conversation
    ↓
Improved Requirement
    ↓
User Approval
    ↓
Update Jira Ticket

The product is NOT intended to replace Jira.

It acts as an AI requirements-quality layer on top of Jira.

---

# 2. MVP Scope

The MVP focuses on:

1. Jira ticket retrieval
2. Requirement analysis
3. Readiness scoring
4. Missing-information detection
5. Dependency awareness
6. AI clarification questions
7. Interactive coaching
8. Development-ready requirement generation
9. Optional company/project knowledge through RAG
10. User-approved Jira update

Do NOT add unnecessary enterprise features.

Do NOT build:

- Multi-company administration
- Complex team management
- Advanced permissions management
- Full Jira replacement functionality
- General project management features
- Complex analytics dashboards
- Automatic Jira synchronisation
- Autonomous Jira ticket modification

---

# 3. Target User

Primary user:

A person responsible for writing or refining software requirements.

This may be:

- Product Manager
- Project Manager
- Founder
- Generalist PM
- Engineer acting as requirements owner
- Business Analyst where one exists

The target startup environment may not have a dedicated Business Analyst.

---

# 4. Technology Stack

## Frontend

- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- React Query
- Vercel

## Backend

- Python
- FastAPI
- REST API
- Pydantic
- LangChain
- LangGraph
- Render

## Database

- PostgreSQL
- Supabase
- Supabase Auth

## AI

Primary LLM:

- Anthropic Claude Sonnet family, using the currently available production model configured for the project.

Embedding model:

- OpenAI text-embedding-3-small

Vector database:

- ChromaDB

## External Integration

- Jira REST API
- Jira OAuth 2.0 / 3LO

## Development

- VS Code
- Claude Code
- GitHub
- Postman

---

# 5. Architecture

Use a modular monolith architecture.

Frontend:

React
    ↓
FastAPI REST API
    ↓
Application Services
    ↓
AI / Jira / RAG / Database modules

Keep the system modular inside one backend application.

Do NOT create microservices.

---

# 6. Backend Structure

The current backend uses the following modular monolith structure:

ai-requirements-coach/
├── app/
│   ├── main.py
│   ├── agent/
│   ├── analysis/
│   ├── auth/
│   ├── coaching/
│   ├── core/
│   ├── database/
│   ├── jira/
│   ├── rag/
│   └── tickets/
│
├── tests/
├── .env
├── .env.example
├── .gitignore
├── CLAUDE.md
├── README.md
└── requirements.txt

Responsibilities:

- `agent/` → LangGraph workflow and LLM orchestration
- `analysis/` → requirement analysis schemas and API routes
- `coaching/` → clarification conversation logic, state, selection, stop conditions, and API routes
- `auth/` → authentication-related functionality
- `core/` → configuration and shared application settings
- `database/` → database access and persistence
- `jira/` → Jira OAuth and Jira REST API integration
- `rag/` → document ingestion, embeddings, retrieval, and ChromaDB
- `tickets/` → ticket-related models and services

Keep responsibilities separated.

Do not create duplicate modules for functionality that already exists.

Routes should handle HTTP requests.

Application logic should remain inside the appropriate module.

Agents should contain LangGraph/LLM orchestration.

Jira modules should contain Jira-specific API logic.

RAG modules should contain retrieval and embedding logic.

Database modules should contain database operations.

---

# 7. Development Strategy

Development is incremental. Do not rewrite completed phases.

## Completed

### Phase 1: Core AI Analysis

Completed:

- Mock ticket input
- Claude integration
- Structured output using forced tool use
- Four readiness criteria
- Overall readiness calculation in Python
- Gap identification
- Clarification question generation
- LangGraph single-node analysis workflow
- API endpoint: POST /api/analyse

### Phase 2: Coaching Foundation

Completed:

- Coaching state
- Coaching session API
- Clarification question selection
- User answer handling
- Re-analysis using accumulated clarification history
- Coaching stop-condition logic
- Maximum clarification rounds
- Coaching tests

### Phase 3: RAG Foundation (standalone module + evaluation-scoped prompt integration)

Completed:

- Standalone `app/rag/` module: schemas, chunking, embeddings, ChromaDB-backed store
- Project-scoped document ingestion (chunk, embed, store) via `app/rag/store.py::add_document`
- Project-scoped semantic retrieval via `app/rag/store.py::retrieve`, with `project_id` always enforced as a metadata filter so one project's chunks can never be returned for another
- Typed errors: `EmbeddingError` (embedding failures), `RAGStoreError` (ChromaDB read/write failures)
- RAG tests: chunking, ingestion, retrieval, project_id isolation, metadata preservation, invalid input, embedding failure
- RAG retrieval wired into the analysis pipeline (`app/agent/graph.py`) and coaching finalization (`app/coaching/router.py`), using a **temporary hardcoded `project_id="default"`** (see "Temporary evaluation scope" below)
- Retrieval fails safely: skipped entirely when `OPENAI_API_KEY` is not configured, and any embedding/store failure degrades to "no context" rather than breaking analysis/coaching
- Deterministic prompt-construction tests for the context-injection logic
- A manual, non-CI with-RAG vs. without-RAG comparison script (`scripts/rag_eval.py`)

### Temporary evaluation scope: `project_id="default"`

This is a deliberate, explicitly scoped exception to the rule in section 20
and section 28 below: RAG prompt integration was implemented ahead of real
Jira/frontend project context, using a single hardcoded constant
(`project_id="default"`) purely so retrieval quality and prompt
integration could be evaluated now, rather than blocked on Jira/frontend
work.

This is temporary scaffolding, not a designed feature:

- The constant lives in one place, clearly named and commented as
  temporary (`app/agent/rag_integration.py`).
- No new required fields were added to `TicketInput`, `MessageRequest`, or
  any other request schema — the constant is resolved internally, never
  accepted from a caller.
- It must be replaced by a real `project_id` sourced from the Jira/frontend
  workflow before RAG integration is considered production-ready. Do not
  extend this pattern elsewhere (no additional hardcoded project ids, no
  features built around `"default"` as if it were a real project).

Now implemented (see docs/architecture.md):

- `POST /api/knowledge/upload` (`app/rag/router.py`) — a real API router for RAG document ingestion
- `TicketInput` now has a `project_id` field (`app/analysis/schemas.py`). For Jira-imported
  tickets, `project_id` comes from the selected Jira project and is threaded through to RAG
  retrieval (`app/agent/graph.py::retrieve_context_node`,
  `app/coaching/router.py::finalize_coaching_session`)
- `TEMP_EVAL_PROJECT_ID` remains, but only as the fallback for manually-entered tickets, which
  have no `project_id` — it is no longer the only path

## Current Priority

The core AI analysis, coaching foundation, and RAG foundation (including
evaluation-scoped prompt integration) are implemented.

The immediate product priority is frontend integration.

The frontend should consume the real backend APIs instead of mock analysis/coaching data.

Replacing the temporary `project_id="default"` constant with real project
context from the frontend/Jira workflow is required before RAG can be
considered production-ready — track this alongside frontend/Jira
integration, not as a separate later phase.

Do not rebuild the existing AI analysis, coaching, or RAG functionality unless a concrete bug or missing requirement is identified.

## Remaining Implementation Order

1. Frontend integration
2. Jira integration
3. (Done, for Jira-imported tickets) Replace the temporary `project_id="default"` RAG scaffolding
   with real project context from Jira/frontend — `TicketInput.project_id` now flows from the
   selected Jira project into `retrieve_context_node`/`finalize_coaching_session`;
   `TEMP_EVAL_PROJECT_ID` remains only as the fallback for manually-entered tickets
4. User-approved Jira update
5. End-to-end testing
6. Deployment

The exact order may be adjusted when required by integration dependencies, but scope must remain MVP-focused.

---

# 8. Readiness Scoring

The ticket is evaluated using four criteria.

## Requirement Clarity

Does the requirement clearly explain what needs to be built?

## Acceptance Criteria

Does the ticket contain clear, measurable and testable acceptance criteria?

## Open Questions

Are important unknowns or ambiguities still unresolved?

## Scope Definition

Is the scope clear and are unnecessary requirements or scope creep avoided?

Each criterion receives a score from 0 to 3.

### Score meanings

0 = Major information is missing; development cannot reasonably begin
1 = Several important questions or ambiguities remain
2 = Mostly clear; only minor questions or ambiguities remain
3 = Clear and sufficiently defined for development

### Overall Readiness

Overall readiness = average of the four criteria, expressed on the same 0-3 scale.

Formula:

Overall Readiness =
(Requirement Clarity +
 Acceptance Criteria +
 Open Questions +
 Scope Definition) / 4

Example:

Requirement Clarity = 1
Acceptance Criteria = 0
Open Questions = 1
Scope Definition = 2

Overall Readiness = (1 + 0 + 1 + 2) / 4
Overall Readiness = 1.0

The readiness scale is 0.0 to 3.0.

Every score must include evidence explaining why the score was assigned.

---

# 9. Analysis Output

The analysis should identify:

- What is clear
- What is missing
- What is ambiguous
- What assumptions exist
- Possible dependencies
- Scope problems
- Missing acceptance criteria
- Important open questions

The output must be structured JSON wherever possible.

Do not rely on parsing arbitrary natural-language responses when structured output is available.

---

# 10. AI Coaching Agent

The AI coach is the main differentiating feature.

It should behave like a requirements coach, not a generic chatbot.

The agent:

1. Reads the analysed ticket
2. Identifies the most important unresolved issue
3. Generates a focused clarification question
4. Explains why the question matters
5. Receives the user's answer
6. Updates the requirement state
7. Determines whether more clarification is needed
8. Asks the next question
9. Re-evaluates readiness
10. Produces the improved requirement

Example:

AI:

"What event should trigger the notification?"

Why:

"The current requirement says 'when something happens', but the triggering event is not defined."

User:

"When a new message is received."

The agent should incorporate this information into the requirement state.

---

# 11. LangGraph

Use LangGraph to represent the coaching workflow as a stateful graph.

Conceptually:

START
 ↓
Analyze Requirement
 ↓
Identify Gaps
 ↓
Generate Question
 ↓
Wait for User
 ↓
Process Answer
 ↓
Update Requirement
 ↓
Re-evaluate
 ↓
More Gaps?
 ├── YES → Generate Next Question
 └── NO → Generate Final Requirement
 ↓
END

The graph should maintain state across the conversation.

Do not build an unnecessarily complicated multi-agent system.

Use one primary requirements-coaching agent with structured states/nodes.

---

# 12. Coaching Stop Condition

The agent should not ask endless questions.

Stop when:

- Important requirement gaps are resolved
- The four readiness criteria reach an acceptable level
- The ticket is sufficiently clear for development

The MVP should use a maximum number of clarification questions to prevent infinite conversations.

Default target:

5 questions maximum.

The system should prioritise the highest-impact unresolved issue first.

---

# 13. Dependency Detection

Dependencies are important because a Jira ticket may depend on other Jira issues.

Examples:

REQ-101: Create Notification API
REQ-102: Create Notification Settings
REQ-103: Add Push Notification Support

REQ-103 may depend on REQ-101 and REQ-102 even if its description does not explicitly mention them.

The system should therefore use available Jira relationship information where possible.

Potential sources:

- Jira linked issues
- Parent/child relationships
- Blocks / is blocked by
- Relates to
- Epic relationships
- Issue descriptions
- Issue keys mentioned in text
- Related tickets retrieved from Jira

The AI should NOT invent dependencies.

If Jira provides evidence of a relationship, provide it to the agent.

If the relationship is inferred from content, mark it as a possible dependency rather than a confirmed dependency.

---

# 14. Jira Integration

Use Jira Cloud REST API.

Authentication:

Jira OAuth 2.0 / 3LO.

High-level flow:

User
 ↓
AI Requirements Coach
 ↓
Jira OAuth
 ↓
User grants permission
 ↓
Authorization code
 ↓
FastAPI callback
 ↓
Access / refresh tokens
 ↓
Retrieve accessible Jira resources
 ↓
Retrieve cloud ID
 ↓
Jira REST API

The backend uses the user's authorised Jira connection to retrieve permitted projects and issues.

The frontend must never contain the Jira client secret.

---

# 15. Jira Project and Ticket Workflow

After Jira connection:

1. Retrieve projects the user can access.
2. Display accessible projects.
3. User selects a project.
4. Retrieve issues for that project.
5. Display Jira status separately from AI review status.
6. User selects a ticket.
7. Retrieve complete ticket information.
8. Retrieve linked issues/dependency information where available.
9. Analyse the requirement.

Do not build a full Jira replacement UI.

The application only needs enough Jira functionality to support requirements refinement.

---

# 16. Jira Status vs AI Review Status

Keep these separate.

Jira Status:

- Backlog
- To Do
- In Progress
- Ready for QA
- Done

AI Review Status:

- Not Reviewed
- Needs Clarification
- Coaching
- Ready

The AI review status belongs to AI Requirements Coach.

The Jira status belongs to Jira.

Do not combine them.

Users may technically select any accessible ticket.

However, requirements refinement is primarily intended for tickets before development.

---

# 17. Jira Updates

IMPORTANT:

Never automatically overwrite a Jira ticket after AI analysis.

The workflow must be:

Jira Ticket
 ↓
AI Analysis
 ↓
AI Coaching
 ↓
Improved Requirement
 ↓
User Reviews
 ↓
User Approves
 ↓
Jira Update

Only update Jira after explicit user approval.

---

# 18. RAG

RAG is an optional contextual knowledge layer.

Purpose:

Allow the AI to use company and project-specific documentation when analysing requirements.

Potential documents:

Company-level:

- Definition of Ready
- Security guidelines
- Engineering standards
- Company policies

Project-level:

- Project requirements
- Architecture guidelines
- Product rules
- Notification rules
- Authentication rules

The system should associate knowledge with the appropriate company/project context.

For the MVP, support a simple project-scoped knowledge model. Do not implement full multi-tenant company management

The AI must retrieve relevant documents for the selected project.

Do not mix unrelated project knowledge.

---

# 19. RAG Architecture

Document
 ↓
Text extraction
 ↓
Chunking
 ↓
OpenAI Embedding
 ↓
Vector
 ↓
ChromaDB
 ↓
Metadata filtering
 ↓
Semantic retrieval
 ↓
Relevant context
 ↓
Claude
 ↓
Requirement analysis

Metadata should identify the relevant scope.

For example:

{
  "project_id": "...",
  "document_type": "security_guideline"
}

Project-specific knowledge must not be retrieved for another project.

---

# 20. RAG Implementation Strategy

RAG must not block the core product workflow.

The implementation priority is:

1. Core AI analysis
2. Coaching loop
3. Frontend integration
4. Jira integration
5. RAG
6. User-approved Jira update
7. End-to-end testing
8. Deployment

RAG should be implemented only after the core Jira-to-coaching workflow is functional.

For the MVP, RAG should remain project-scoped and minimal.

Do not introduce RAG into the analysis pipeline until the retrieval quality and metadata filtering can be tested reliably.

Exception (Phase 3 evaluation): RAG retrieval has been integrated into the
analysis and coaching-finalization prompts using a temporary, explicitly
labeled `project_id="default"` constant, specifically to evaluate
retrieval quality and prompt integration before real project context
exists. See section 7 and docs/architecture.md for what this covers and
its temporary status. This does not change the rule for any other
integration — do not hardcode identifiers elsewhere to force integration.

---

# 21. Database

Use PostgreSQL through Supabase.

Potential entities:

- users
- jira_connections
- projects
- requirements
- jira_issues
- analyses
- coaching_sessions
- coaching_messages
- documents

Keep the schema minimal.

Do not build unnecessary multi-tenant functionality for the MVP.

---

# 22. Security

Never expose:

- Anthropic API key
- OpenAI API key
- Jira client secret
- Supabase secret key

to the frontend.

Secrets must remain in backend environment variables.

Use:

- `.env`
- `.gitignore`
- backend-only secret access

Never commit secrets to GitHub.

---

# 23. Environment Variables

Expected environment variables may include:

ANTHROPIC_API_KEY=
OPENAI_API_KEY=

SUPABASE_URL=
SUPABASE_PUBLISHABLE_KEY=
SUPABASE_SECRET_KEY=

DATABASE_URL=

JIRA_CLIENT_ID=
JIRA_CLIENT_SECRET=
JIRA_REDIRECT_URI=

Do not hardcode secrets.

---

# 24. API Design

Use REST endpoints.

Example endpoints:

GET /health

POST /api/analyse

POST /api/coaching/start

POST /api/coaching/{session_id}/message

GET /api/coaching/{session_id}

POST /api/requirements/{id}/approve

GET /api/jira/projects

GET /api/jira/projects/{project_id}/issues

GET /api/jira/issues/{issue_key}

GET /api/jira/issues/{issue_key}/links

POST /api/jira/issues/{issue_key}/update

Do not implement every endpoint immediately.

Build only what is required for the current milestone.

---

# 25. Error Handling

The application must handle:

- LLM failures
- Invalid LLM responses
- Jira API failures
- Jira authentication failures
- Expired Jira tokens
- Missing permissions
- Missing ticket data
- Empty requirements
- RAG retrieval failures
- Database failures

Do not allow one external service failure to crash the entire application.

Return useful error messages.

---

# 26. Testing Strategy

Prioritise testing the core AI workflow.

Test cases should include:

1. Clear ticket
2. Very vague ticket
3. Missing acceptance criteria
4. Missing scope
5. Multiple open questions
6. Ticket with dependencies
7. Ticket with linked Jira issues
8. Already reviewed ticket
9. Failed Jira request
10. LLM failure

The scoring behaviour should be deterministic enough to evaluate consistently.

---

# 27. Development Principles

Prioritise:

1. Correctness
2. Simplicity
3. Testability
4. Explainability
5. MVP scope

Do not over-engineer.

Do not introduce new frameworks without a clear reason.

Do not create unnecessary abstractions.

Do not build features that are not required for the MVP.

When uncertain about a technical decision, prefer the simpler implementation that can be tested quickly.

---

# 28. Current Implementation Priority

The core backend AI analysis, coaching foundation, and standalone RAG
foundation are implemented.

The immediate product priority is integrating the real backend with the
frontend.

Current workflow:

FRONTEND
 ↓
FastAPI API
 ↓
AI ANALYSIS
 ↓
READINESS SCORE
 ↓
GAPS
 ↓
COACHING
 ↓
USER ANSWER
 ↓
RE-EVALUATION
 ↓
IMPROVED REQUIREMENT

The next implementation stages are:

1. Frontend integration with existing analysis/coaching APIs
2. Jira OAuth and Jira project/ticket retrieval
3. Connect Jira tickets and project context to the existing analysis workflow, replacing the temporary `project_id="default"` RAG constant with real project context
4. (Done, evaluation-scoped) RAG retrieval wired into analysis/coaching — see section 7
5. Improved requirement review and explicit approval
6. User-approved Jira update
7. End-to-end testing
8. Deployment

Important dependency:

RAG prompt integration now exists, but only against a temporary hardcoded
`project_id="default"` constant (see section 7) — explicitly for
evaluating retrieval quality before real project context exists. This is
scaffolding, not a production design: it must be replaced by a reliable
project_id sourced from the frontend/Jira workflow before RAG can be
considered production-ready, and this hardcode-a-project-id shortcut must
not be reused elsewhere.

Do not rebuild completed backend functionality unless required to support
an integration.

---

# 29. Important Rule

The real implementation must replace mock behaviour with actual backend APIs gradually.

During integration phases, test each boundary between frontend and backend before moving to the next feature.

Do not modify the UI just because a backend feature is not implemented yet.

Do not rebuild working backend functionality when an existing API already provides the required capability.

---

# 30. Claude Code Behaviour

Before implementing a new feature:

1. Inspect the existing code.
2. Understand the current architecture.
3. Do not rewrite working code unnecessarily.
4. Keep changes focused.
5. Explain important architectural changes.
6. Add tests for core functionality.
7. Run the relevant tests after changes.
8. Do not introduce unrelated features.

When integrating existing modules:

1. Inspect the existing implementation first.
2. Reuse existing schemas, endpoints, and services.
3. Do not create duplicate functionality.
4. Preserve existing tests and behaviour.
5. Add integration tests where appropriate.
6. If an existing API does not provide information required by the frontend, extend it minimally rather than creating a parallel implementation.

# 31. Documentation Maintenance

The following documentation files must remain synchronized with the implementation:

- `CLAUDE.md` → project rules, scope, priorities, and development instructions
- `docs/architecture.md` → current implemented architecture and system/data flows
- `docs/skills.md` → reusable technical patterns, implementation conventions, and integration knowledge

When implementing a feature that changes architecture, update `docs/architecture.md`.

When implementing a new technical pattern, integration, library usage, or reusable implementation convention, update `docs/skills.md`.

When implementation progress changes the current project phase, priorities, constraints, or development rules, update `CLAUDE.md`.

Documentation updates must:

1. Reflect the actual implemented code.
2. Never document planned functionality as if it already exists.
3. Avoid unnecessary duplication between the three files.
4. Keep documentation concise and maintainable.
5. Be included in the same change as the implementation that caused the documentation to become outdated.

Before completing a feature, check whether any of these documentation files need updating.

If documentation changes are required, make them as part of the same implementation task and report them in the final summary.

If a requirement is ambiguous, choose the simplest MVP-compatible interpretation and state the assumption.

Do not expand the scope without explicit instruction.