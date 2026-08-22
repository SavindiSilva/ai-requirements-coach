"""FastAPI routes for the Phase 2 coaching workflow.

Phase 2A covers the first step of the multi-turn coaching loop: run the
existing Phase 1 analysis, pick the weakest criterion, and ask one focused
clarification question.

Phase 2B covers the second step: receive and store the user's answer to
that question.

Phase 2C covers the third step: re-run the Phase 1 analysis using the
original ticket plus the accumulated coaching Q&A history, and replace the
session's analysis with the result.

Phase 2D covers the fourth step: given the re-analysed ticket, decide
deterministically (no Claude call) whether coaching should stop. If not,
generate exactly one next clarification question via the same pipeline as
Phase 2A.

Phase 2E covers the fifth step: once coaching is complete, synthesise the
original ticket plus the accumulated coaching history into a structured,
development-ready requirement via one Claude call, and store it on the
session. Idempotent - a session that already has a final requirement
returns the stored result without calling Claude again. User approval
and persistence are later milestones.
"""

from fastapi import APIRouter, HTTPException

from app.agent.graph import analyze_ticket
from app.agent.llm import LLMAnalysisError
from app.agent.rag_integration import TEMP_EVAL_PROJECT_ID, get_retrieved_context
from app.analysis.schemas import TicketInput
from app.coaching.llm import (
    CoachingLLMError,
    generate_clarification_question,
    generate_final_requirement,
)
from app.coaching.prompts import (
    build_finalize_system_prompt,
    build_finalize_user_prompt,
    build_question_system_prompt,
    build_question_user_prompt,
)
from app.coaching.schemas import (
    CoachingMessageResponse,
    CoachingNextResponse,
    CoachingStartResponse,
    CurrentScores,
    FinalizeResponse,
    MessageRequest,
    ReanalyzeResponse,
)
from app.coaching.selection import gather_relevant_issues, select_weakest_criterion
from app.coaching.stop_condition import compute_remaining_gaps, should_stop_coaching
from app.coaching.store import (
    CoachingAlreadyCompleteError,
    CoachingNotCompleteError,
    InconsistentHistoryError,
    NoAnsweredQuestionsError,
    NoUnansweredQuestionError,
    PendingQuestionError,
    SessionNotFoundError,
    create_session,
    get_session_for_finalize,
    get_session_for_next,
    get_session_for_reanalysis,
    mark_coaching_complete,
    record_answer,
    replace_analysis,
    set_next_question,
    store_final_requirement,
)

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

    session_id = create_session(ticket, analysis, question_output.question, question_output.why)

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


@router.post("/coaching/{session_id}/reanalyze", response_model=ReanalyzeResponse)
def reanalyze_coaching_session(session_id: str) -> ReanalyzeResponse:
    try:
        session = get_session_for_reanalysis(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (NoAnsweredQuestionsError, InconsistentHistoryError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    coaching_history = list(zip(session["questions_asked"], session["answers"]))

    try:
        new_analysis = analyze_ticket(session["ticket"], coaching_history=coaching_history)
    except LLMAnalysisError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    session = replace_analysis(session_id, new_analysis)

    return ReanalyzeResponse(
        session_id=session_id,
        analysis=session["analysis"],
        question_count=session["question_count"],
        questions_asked=session["questions_asked"],
        answers=session["answers"],
    )


@router.post("/coaching/{session_id}/message", response_model=CoachingMessageResponse)
def submit_coaching_message(session_id: str, message: MessageRequest) -> CoachingMessageResponse:
    try:
        session = record_answer(session_id, message.answer)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NoUnansweredQuestionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    analysis = session["analysis"]

    return CoachingMessageResponse(
        session_id=session_id,
        question=session["questions_asked"][-1],
        answer=session["answers"][-1],
        question_count=session["question_count"],
        questions_asked=session["questions_asked"],
        answers=session["answers"],
        current_scores=CurrentScores(
            requirement_clarity=analysis.requirement_clarity.score,
            acceptance_criteria=analysis.acceptance_criteria.score,
            open_questions=analysis.open_questions.score,
            scope_definition=analysis.scope_definition.score,
        ),
    )


@router.post("/coaching/{session_id}/next", response_model=CoachingNextResponse)
def next_coaching_step(session_id: str) -> CoachingNextResponse:
    try:
        session = get_session_for_next(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        CoachingAlreadyCompleteError,
        PendingQuestionError,
        InconsistentHistoryError,
        NoAnsweredQuestionsError,
    ) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    analysis = session["analysis"]
    current_scores = CurrentScores(
        requirement_clarity=analysis.requirement_clarity.score,
        acceptance_criteria=analysis.acceptance_criteria.score,
        open_questions=analysis.open_questions.score,
        scope_definition=analysis.scope_definition.score,
    )

    should_stop, stop_reason = should_stop_coaching(analysis, session["question_count"])

    if should_stop:
        session = mark_coaching_complete(session_id, stop_reason)
        return CoachingNextResponse(
            session_id=session_id,
            is_complete=True,
            stop_reason=stop_reason,
            question=None,
            why=None,
            question_count=session["question_count"],
            current_scores=current_scores,
        )

    criterion_key = select_weakest_criterion(analysis)
    issues = gather_relevant_issues(analysis, criterion_key)

    system_prompt = build_question_system_prompt()
    user_prompt = build_question_user_prompt(
        session["ticket"],
        analysis,
        criterion_key,
        issues,
        previous_questions=session["questions_asked"],
    )

    try:
        question_output = generate_clarification_question(system_prompt, user_prompt)
    except CoachingLLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    session = set_next_question(session_id, question_output.question, question_output.why)

    return CoachingNextResponse(
        session_id=session_id,
        is_complete=False,
        stop_reason=None,
        question=question_output.question,
        why=question_output.why,
        question_count=session["question_count"],
        current_scores=current_scores,
    )


@router.post("/coaching/{session_id}/finalize", response_model=FinalizeResponse)
def finalize_coaching_session(session_id: str) -> FinalizeResponse:
    try:
        session = get_session_for_finalize(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (CoachingNotCompleteError, InconsistentHistoryError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    analysis = session["analysis"]
    remaining_gaps = compute_remaining_gaps(analysis)
    current_scores = CurrentScores(
        requirement_clarity=analysis.requirement_clarity.score,
        acceptance_criteria=analysis.acceptance_criteria.score,
        open_questions=analysis.open_questions.score,
        scope_definition=analysis.scope_definition.score,
    )

    if session["final_requirement"] is None:
        coaching_history = list(zip(session["questions_asked"], session["answers"]))

        ticket = session["ticket"]
        query_text = f"{ticket.title}\n{ticket.description}"
        project_id = ticket.project_id or TEMP_EVAL_PROJECT_ID
        retrieved_context = get_retrieved_context(query_text, project_id=project_id)

        system_prompt = build_finalize_system_prompt()
        user_prompt = build_finalize_user_prompt(
            ticket, analysis, coaching_history, session["stop_reason"], retrieved_context
        )

        try:
            final_requirement = generate_final_requirement(system_prompt, user_prompt)
        except CoachingLLMError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        session = store_final_requirement(session_id, final_requirement)

    return FinalizeResponse(
        session_id=session_id,
        is_complete=session["is_complete"],
        stop_reason=session["stop_reason"],
        final_requirement=session["final_requirement"],
        remaining_gaps=remaining_gaps,
        current_scores=current_scores,
        question_count=session["question_count"],
    )
