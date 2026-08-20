"""LangGraph state for the Phase 1 single-shot analysis graph."""

from typing import TypedDict

from app.analysis.schemas import AnalysisResult, TicketInput
from app.rag.schemas import RetrievedChunk


class AgentState(TypedDict):
    ticket: TicketInput
    analysis: AnalysisResult | None
    # Optional accumulated coaching Q&A history (Phase 2C re-analysis).
    # None for a plain Phase 1 analysis — output is identical to before.
    coaching_history: list[tuple[str, str]] | None
    # Phase 3: chunks retrieved by retrieve_context_node, or None/[] if RAG
    # found nothing or failed (retrieval always fails safe - see
    # app/agent/rag_integration.py). Consumed by analyze_requirement_node.
    retrieved_context: list[RetrievedChunk] | None
