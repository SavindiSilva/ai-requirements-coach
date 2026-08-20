"""Deterministic tests for Phase 3 RAG prompt integration.

Covers app/agent/rag_integration.py (the fail-safe retrieval wrapper and
prompt-context formatting) and its wiring into app/agent/prompts.py,
app/agent/graph.py, and app/coaching/prompts.py.

These tests construct RetrievedChunk objects directly and never call a real
embedding API - they test prompt-string construction and fail-safe
behaviour, mirroring the "pure and LLM-free by design" testing convention
already used for app/coaching/selection.py and app/coaching/stop_condition.py.

tests/test_analysis.py and tests/test_coaching.py are untouched - this file
is additive only, per the Phase 3 constraint to preserve existing tests.

One test (test_analyze_ticket_still_succeeds_when_rag_retrieval_raises) does
hit the real Claude API, matching the existing no-mocking convention for
Claude calls - it exists specifically to prove the full analysis pipeline
degrades gracefully when RAG retrieval itself fails, which is the core
regression this integration must never introduce.
"""

import app.agent.rag_integration as rag_integration
from app.agent.graph import analyze_ticket, retrieve_context_node
from app.agent.prompts import build_user_prompt
from app.agent.rag_integration import format_context_for_prompt, get_retrieved_context
from app.agent.state import AgentState
from app.analysis.schemas import AnalysisResult, CriterionScore, TicketInput
from app.coaching.prompts import build_finalize_user_prompt
from app.core.config import settings
from app.rag.embeddings import EmbeddingError
from app.rag.schemas import ChunkMetadata, DocumentType, RetrievedChunk
from app.rag.store import RAGStoreError

TICKET = TicketInput(title="Add refund flow", description="Users can request refunds.")


def _make_chunk(
    text: str = "Refunds over $500 require manager approval.",
    title: str = "Refund Policy",
) -> RetrievedChunk:
    return RetrievedChunk(
        text=text,
        metadata=ChunkMetadata(
            project_id="default",
            document_id="doc-1",
            document_type=DocumentType.PRODUCT_RULE,
            title=title,
            chunk_index=0,
        ),
        distance=0.1,
    )


def _make_analysis(rc: int = 2, ac: int = 2, oq: int = 2, sd: int = 2) -> AnalysisResult:
    return AnalysisResult(
        requirement_clarity=CriterionScore(score=rc, evidence="evidence"),
        acceptance_criteria=CriterionScore(score=ac, evidence="evidence"),
        open_questions=CriterionScore(score=oq, evidence="evidence"),
        scope_definition=CriterionScore(score=sd, evidence="evidence"),
        overall_readiness=round((rc + ac + oq + sd) / 4, 2),
    )


# --- format_context_for_prompt ---------------------------------------------


def test_format_context_for_prompt_empty_returns_empty_string():
    assert format_context_for_prompt([]) == ""


def test_format_context_for_prompt_includes_title_type_and_text():
    formatted = format_context_for_prompt([_make_chunk()])

    assert "Refund Policy" in formatted
    assert "product_rule" in formatted
    assert "Refunds over $500 require manager approval." in formatted


# --- build_user_prompt (analysis) ------------------------------------------


def test_build_user_prompt_includes_context_section_when_provided():
    prompt = build_user_prompt(TICKET, retrieved_context=[_make_chunk()])

    assert "Relevant project context" in prompt
    assert "Refund Policy" in prompt


def test_build_user_prompt_omits_context_section_when_none():
    prompt = build_user_prompt(TICKET, retrieved_context=None)
    assert "Relevant project context" not in prompt


def test_build_user_prompt_omits_context_section_when_empty_list():
    prompt = build_user_prompt(TICKET, retrieved_context=[])
    assert "Relevant project context" not in prompt


def test_build_user_prompt_default_call_shape_is_unaffected():
    # Same call shape as every pre-Phase-3 caller: no coaching_history, no
    # retrieved_context. Existing callers never pass retrieved_context, so
    # this must behave exactly as before.
    prompt = build_user_prompt(TICKET)

    assert "Analyze this ticket" in prompt
    assert "Relevant project context" not in prompt
    assert "Previous clarification" not in prompt


# --- build_finalize_user_prompt (coaching) ----------------------------------


def test_build_finalize_user_prompt_includes_context_section_when_provided():
    prompt = build_finalize_user_prompt(
        TICKET,
        _make_analysis(),
        [],
        stop_reason="readiness_threshold_met",
        retrieved_context=[_make_chunk()],
    )

    assert "Relevant project context" in prompt
    assert "Refund Policy" in prompt


def test_build_finalize_user_prompt_omits_context_section_when_none():
    prompt = build_finalize_user_prompt(
        TICKET,
        _make_analysis(),
        [],
        stop_reason="readiness_threshold_met",
        retrieved_context=None,
    )

    assert "Relevant project context" not in prompt


# --- get_retrieved_context: fail-safe behaviour -----------------------------


def test_get_retrieved_context_short_circuits_when_no_openai_key(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("retrieve() must not be called when openai_api_key is empty")

    monkeypatch.setattr(rag_integration, "retrieve", _fail_if_called)

    assert get_retrieved_context("some query") == []


def test_get_retrieved_context_returns_empty_on_embedding_error(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-fake-for-this-test")
    monkeypatch.setattr(
        rag_integration, "retrieve", lambda *a, **k: (_ for _ in ()).throw(EmbeddingError("boom"))
    )

    assert get_retrieved_context("some query") == []


def test_get_retrieved_context_returns_empty_on_store_error(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-fake-for-this-test")
    monkeypatch.setattr(
        rag_integration, "retrieve", lambda *a, **k: (_ for _ in ()).throw(RAGStoreError("boom"))
    )

    assert get_retrieved_context("some query") == []


def test_get_retrieved_context_returns_empty_on_value_error(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-fake-for-this-test")
    monkeypatch.setattr(
        rag_integration, "retrieve", lambda *a, **k: (_ for _ in ()).throw(ValueError("boom"))
    )

    assert get_retrieved_context("some query") == []


def test_get_retrieved_context_returns_chunks_on_success(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-fake-for-this-test")
    expected = [_make_chunk()]
    monkeypatch.setattr(rag_integration, "retrieve", lambda *a, **k: expected)

    assert get_retrieved_context("some query") == expected


# --- retrieve_context_node (graph) regression coverage ----------------------


def test_retrieve_context_node_never_raises_when_rag_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")

    state: AgentState = {
        "ticket": TICKET,
        "analysis": None,
        "coaching_history": None,
        "retrieved_context": None,
    }

    assert retrieve_context_node(state) == {"retrieved_context": []}


# --- full pipeline regression (real Claude call, RAG forced to fail) -------


def test_analyze_ticket_still_succeeds_when_rag_retrieval_raises(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-fake-for-this-test")
    monkeypatch.setattr(
        rag_integration, "retrieve", lambda *a, **k: (_ for _ in ()).throw(RAGStoreError("chromadb is down"))
    )

    result = analyze_ticket(TICKET)

    assert 0 <= result.overall_readiness <= 3
