"""LangGraph state for the Phase 1 single-shot analysis graph."""

from typing import TypedDict

from app.analysis.schemas import AnalysisResult, TicketInput


class AgentState(TypedDict):
    ticket: TicketInput
    analysis: AnalysisResult | None
