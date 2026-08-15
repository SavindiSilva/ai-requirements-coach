"""FastAPI routes for ticket analysis (Phase 1: single-shot, no persistence)."""

from fastapi import APIRouter, HTTPException

from app.agent.graph import analyze_ticket
from app.agent.llm import LLMAnalysisError
from app.analysis.schemas import AnalysisResult, TicketInput

router = APIRouter()


@router.post("/analyse", response_model=AnalysisResult)
def analyse_ticket(ticket: TicketInput) -> AnalysisResult:
    try:
        return analyze_ticket(ticket)
    except LLMAnalysisError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
