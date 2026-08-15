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

Use a structure similar to:

ai-requirements-coach/
├── app/
│   ├── main.py
│   ├── config.py
│   │
│   ├── api/
│   │   └── routes/
│   │
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── agent/
│   ├── jira/
│   ├── rag/
│   └── db/
│
├── tests/
├── .env
├── .gitignore
└── requirements.txt

Keep responsibilities separated.

Routes should handle HTTP requests.

Services should contain application logic.

Agents should contain LangGraph/LLM orchestration.

Jira modules should contain Jira-specific API logic.

RAG modules should contain retrieval and embedding logic.

Database modules should contain database operations.

---

# 7. Development Strategy

Build in this order.

## Phase 1: Core AI Agent

First build the AI agent using MOCK ticket data.

Do NOT start by integrating Jira.

The initial input should be plain structured ticket data.

Example:

{
  "title": "Add notification feature",
  "description": "Users should receive notifications when something happens."
}

The agent should return structured analysis.

The first working milestone is:

Ticket
→ Analysis
→ Score
→ Gaps
→ Questions

Only after this works reliably should Jira integration be added.

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

Do NOT build RAG before the core AI agent works.

Order:

1. Mock ticket
2. AI analysis
3. Scoring
4. Coaching
5. Improved ticket
6. Jira integration
7. RAG
8. Frontend integration
9. Deployment

RAG is not required for the first working agent.

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

The current priority is the backend AI agent.

Build this first:

MOCK TICKET
 ↓
LANGGRAPH
 ↓
CLAUDE
 ↓
STRUCTURED ANALYSIS
 ↓
4 CRITERIA SCORES
 ↓
GAPS
 ↓
CLARIFICATION QUESTIONS

After that:

COACHING STATE
 ↓
USER ANSWER
 ↓
RE-EVALUATION
 ↓
IMPROVED REQUIREMENT

Then integrate Jira.

Then implement RAG.

Then connect the React frontend.

Then deploy.

---

# 29. Important Rule

Do not assume that prototype functionality is real backend functionality.

The current UI prototype uses mock data.

The real implementation must replace mock behaviour with actual backend APIs gradually.

Do not modify the UI just because a backend feature is not implemented yet.

Build and test the backend independently first.

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

If a requirement is ambiguous, choose the simplest MVP-compatible interpretation and state the assumption.

Do not expand the scope without explicit instruction.