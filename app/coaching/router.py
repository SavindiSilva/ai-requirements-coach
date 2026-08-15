"""FastAPI routes for the Phase 2A coaching workflow.

Phase 2A only covers the first step of the multi-turn coaching loop:
run the existing Phase 1 analysis, pick the weakest criterion, and ask one
focused clarification question. Receiving the answer, re-analysis, the stop
condition and the final improved requirement are later milestones.
"""

from fastapi import APIRouter, HTTPException

from app.agent.graph import analyze_ticket
from app.agent.llm import LLMAnalysisError
from app.analysis.schemas import TicketInput
from app.coaching.llm import CoachingLLMError, generate_clarification_question
from app.coaching.prompts import build_question_system_prompt, build_question_user_prompt
from app.coaching.schemas import CoachingStartResponse, CurrentScores
from app.coaching.selection import gather_relevant_issues, select_weakest_criterion
from app.coaching.store import create_session

router = APIRouter()


@router.post("/coaching/start", response_model=CoachingStartResponse)
def start_coaching(ticket: TicketInput) -> CoachingStartResponse:
    try:
        analysis = analyze_ticket(ticket)
    except LLMAnalysisError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    criterion_key = select_weakest_criterion(analysis)
    issues = gather_relevant_issues(analysis, criterion_key)

    system_prompt = build_question_system_prompt()
    user_prompt = build_question_user_prompt(ticket, analysis, criterion_key, issues)

    try:
        question_output = generate_clarification_question(system_prompt, user_prompt)
    except CoachingLLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    session_id = create_session(ticket, analysis)

    return CoachingStartResponse(
        session_id=session_id,
        question=question_output.question,
        why=question_output.why,
        current_scores=CurrentScores(
            requirement_clarity=analysis.requirement_clarity.score,
            acceptance_criteria=analysis.acceptance_criteria.score,
            open_questions=analysis.open_questions.score,
            scope_definition=analysis.scope_definition.score,
        ),
    )
