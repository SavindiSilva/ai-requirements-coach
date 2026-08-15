"""LangGraph state for the Phase 1 single-shot analysis graph."""

from typing import TypedDict

from app.analysis.schemas import AnalysisResult, TicketInput


class AgentState(TypedDict):
    ticket: TicketInput
    analysis: AnalysisResult | None
    # Optional accumulated coaching Q&A history (Phase 2C re-analysis).
    # None for a plain Phase 1 analysis — output is identical to before.
    coaching_history: list[tuple[str, str]] | None
