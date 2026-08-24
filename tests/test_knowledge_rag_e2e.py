"""End-to-end verification of the knowledge pipeline: upload -> chunk ->
embed -> ChromaDB -> retrieval -> analysis/finalize prompt, now that a
ticket's real project_id (sourced from the selected Jira project) is
threaded through instead of always falling back to
app/agent/rag_integration.py's TEMP_EVAL_PROJECT_ID.

Covers:
- app/rag/store.py::add_document / retrieve (unchanged - reused as-is)
- app/agent/rag_integration.py::get_retrieved_context (unchanged - reused as-is)
- app/agent/graph.py::retrieve_context_node (changed: now passes
  ticket.project_id, falling back to TEMP_EVAL_PROJECT_ID only when the
  ticket has none)
- app/coaching/router.py::finalize_coaching_session (same change)

Tests that hit the real OpenAI embedding API and real ChromaDB are gated by
requires_openai, same convention as tests/test_rag.py. The fallback tests
don't need a real embedding call - they only need to prove which project_id
string reaches get_retrieved_context, so they monkeypatch it directly and
run unconditionally.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.agent.graph import retrieve_context_node
from app.agent.prompts import build_user_prompt
from app.agent.rag_integration import TEMP_EVAL_PROJECT_ID, get_retrieved_context
from app.agent.state import AgentState
from app.analysis.schemas import AnalysisResult, CriterionScore, TicketInput
from app.coaching.schemas import FinalRequirementContent
from app.coaching.store import create_session, mark_coaching_complete
from app.core.config import settings
from app.main import app
from app.rag.store import retrieve

requires_openai = pytest.mark.skipif(
    not settings.openai_api_key,
    reason="OPENAI_API_KEY not configured locally - skipping real-embedding RAG tests",
)

client_app = TestClient(app)


def _upload(project_id: str, filename: str, text: bytes, document_type: str, title: str | None = None):
    data = {"project_id": project_id, "document_type": document_type}
    if title:
        data["title"] = title
    response = client_app.post(
        "/api/knowledge/upload",
        files={"file": (filename, text, "text/plain")},
        data=data,
    )
    assert response.status_code == 200
    return response.json()


def _make_analysis(rc: int = 2, ac: int = 2, oq: int = 2, sd: int = 2) -> AnalysisResult:
    return AnalysisResult(
        requirement_clarity=CriterionScore(score=rc, evidence="evidence"),
        acceptance_criteria=CriterionScore(score=ac, evidence="evidence"),
        open_questions=CriterionScore(score=oq, evidence="evidence"),
        scope_definition=CriterionScore(score=sd, evidence="evidence"),
        overall_readiness=round((rc + ac + oq + sd) / 4, 2),
    )


# --- Pipeline sanity: upload -> ChromaDB -> retrieve() -----------------------


@requires_openai
def test_uploaded_document_is_chunked_embedded_stored_and_retrievable_by_project_id():
    project_id = f"e2e-{uuid.uuid4()}"
    _upload(
        project_id,
        "security-standards.txt",
        b"Security Standards: every API endpoint must require authentication "
        b"and must use TLS 1.2 or higher for all traffic.",
        "security_guideline",
        title="Security Standards",
    )

    chunks = retrieve(project_id=project_id, query_text="What are the security requirements for this API?")
    assert len(chunks) >= 1
    assert any("TLS" in chunk.text for chunk in chunks)
    assert all(chunk.metadata.project_id == project_id for chunk in chunks)

    # A different project must never see this project's chunks.
    other_chunks = retrieve(project_id=f"other-{uuid.uuid4()}", query_text="security requirements TLS")
    retrieved_texts = {c.text for c in chunks}
    assert all(c.text not in retrieved_texts for c in other_chunks)


@requires_openai
def test_uploaded_document_reaches_the_analysis_prompt_via_get_retrieved_context():
    project_id = f"e2e-{uuid.uuid4()}"
    _upload(
        project_id,
        "notification-rules.txt",
        b"Notification Rules: push notifications must be opt-in and rate-limited to one per hour per user.",
        "product_rule",
    )

    chunks = get_retrieved_context("Add push notification support", project_id=project_id)
    assert len(chunks) >= 1

    ticket = TicketInput(title="Add push notification support", description="Users should get notified.")
    prompt = build_user_prompt(ticket, retrieved_context=chunks)

    assert "Relevant project context" in prompt
    assert "rate-limited" in prompt


# --- retrieve_context_node: real Jira project_id now reaches retrieval ------


@requires_openai
def test_retrieve_context_node_retrieves_knowledge_uploaded_under_the_tickets_real_project_id():
    project_id = f"e2e-{uuid.uuid4()}"
    _upload(
        project_id,
        "architecture.txt",
        b"Architecture Guideline: all services must communicate over gRPC, never raw HTTP.",
        "architecture_guideline",
    )

    ticket = TicketInput(
        title="Add service-to-service call",
        description="One service should call another.",
        project_id=project_id,
    )
    state: AgentState = {
        "ticket": ticket,
        "analysis": None,
        "coaching_history": None,
        "retrieved_context": None,
    }

    result = retrieve_context_node(state)

    retrieved_texts = " ".join(chunk.text for chunk in result["retrieved_context"])
    assert "gRPC" in retrieved_texts


@requires_openai
def test_retrieve_context_node_does_not_leak_knowledge_across_projects():
    project_a = f"e2e-{uuid.uuid4()}"
    project_b = f"e2e-{uuid.uuid4()}"
    _upload(
        project_a,
        "project-a-only.txt",
        b"Project A Rule: all exports must be watermarked with the account id.",
        "product_rule",
    )

    ticket_for_b = TicketInput(
        title="Add export feature",
        description="Users should be able to export their data.",
        project_id=project_b,
    )
    state: AgentState = {
        "ticket": ticket_for_b,
        "analysis": None,
        "coaching_history": None,
        "retrieved_context": None,
    }

    result = retrieve_context_node(state)

    retrieved_texts = " ".join(chunk.text for chunk in result["retrieved_context"])
    assert "watermarked" not in retrieved_texts


def test_retrieve_context_node_falls_back_to_temp_eval_project_id_when_ticket_has_no_project_id(monkeypatch):
    captured: dict = {}

    def _fake_get_retrieved_context(query_text, project_id=None, k=5):
        captured["project_id"] = project_id
        return []

    monkeypatch.setattr("app.agent.graph.get_retrieved_context", _fake_get_retrieved_context)

    ticket = TicketInput(title="Manually entered ticket", description="No Jira project behind this one.")
    state: AgentState = {
        "ticket": ticket,
        "analysis": None,
        "coaching_history": None,
        "retrieved_context": None,
    }

    retrieve_context_node(state)

    assert captured["project_id"] == TEMP_EVAL_PROJECT_ID


def test_retrieve_context_node_uses_the_tickets_project_id_when_present(monkeypatch):
    captured: dict = {}

    def _fake_get_retrieved_context(query_text, project_id=None, k=5):
        captured["project_id"] = project_id
        return []

    monkeypatch.setattr("app.agent.graph.get_retrieved_context", _fake_get_retrieved_context)

    ticket = TicketInput(title="Jira ticket", description="Imported from Jira.", project_id="PROJ-10001")
    state: AgentState = {
        "ticket": ticket,
        "analysis": None,
        "coaching_history": None,
        "retrieved_context": None,
    }

    retrieve_context_node(state)

    assert captured["project_id"] == "PROJ-10001"


# --- finalize_coaching_session: same project-scoped retrieval --------------


def _create_completed_session(ticket: TicketInput) -> str:
    analysis = _make_analysis()
    session_id = create_session(ticket, analysis, question="unused", why="unused")
    mark_coaching_complete(session_id, "readiness_threshold_met")
    return session_id


_SAMPLE_FINAL_REQUIREMENT = FinalRequirementContent(
    user_story="As a user, I want X so that Y.",
    acceptance_criteria=["Given A, when B, then C."],
    scope=["In scope: X."],
    assumptions=["Assumes Y exists."],
    dependencies=["Depends on Z."],
)


@requires_openai
def test_finalize_coaching_session_uses_the_tickets_real_project_id_for_retrieval(monkeypatch):
    project_id = f"e2e-{uuid.uuid4()}"
    _upload(
        project_id,
        "definition-of-ready.txt",
        b"Definition of Ready: every ticket must specify a rollback plan before development starts.",
        "definition_of_ready",
    )

    ticket = TicketInput(
        title="Add export feature",
        description="Users should be able to export their data.",
        project_id=project_id,
    )
    session_id = _create_completed_session(ticket)

    captured: dict = {}

    def _fake_generate(system_prompt, user_prompt, **kwargs):
        captured["user_prompt"] = user_prompt
        return _SAMPLE_FINAL_REQUIREMENT

    monkeypatch.setattr("app.coaching.router.generate_final_requirement", _fake_generate)

    response = client_app.post(f"/api/coaching/{session_id}/finalize")

    assert response.status_code == 200
    assert "rollback plan" in captured["user_prompt"]


def test_finalize_coaching_session_falls_back_to_temp_eval_project_id_when_ticket_has_no_project_id(monkeypatch):
    ticket = TicketInput(title="Manually entered ticket", description="No Jira project behind this one.")
    session_id = _create_completed_session(ticket)

    captured: dict = {}

    def _fake_get_retrieved_context(query_text, project_id=None, k=5):
        captured["project_id"] = project_id
        return []

    def _fake_generate(system_prompt, user_prompt, **kwargs):
        return _SAMPLE_FINAL_REQUIREMENT

    monkeypatch.setattr("app.coaching.router.get_retrieved_context", _fake_get_retrieved_context)
    monkeypatch.setattr("app.coaching.router.generate_final_requirement", _fake_generate)

    response = client_app.post(f"/api/coaching/{session_id}/finalize")

    assert response.status_code == 200
    assert captured["project_id"] == TEMP_EVAL_PROJECT_ID
