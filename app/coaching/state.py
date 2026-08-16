"""In-memory coaching session state shape (Phase 2A).

TODO(Phase 2B / persistence): this TypedDict backs an in-memory-only session
store (see app/coaching/store.py). Once database persistence is added (see
CLAUDE.md section 21, `coaching_sessions` / `coaching_messages` tables), this
should be replaced by a DB-backed model instead of a process-local dict.
"""

from typing import TypedDict

from app.analysis.schemas import AnalysisResult, TicketInput


class CoachingSessionState(TypedDict):
    ticket: TicketInput
    analysis: AnalysisResult
    questions_asked: list[str]
    answers: list[str]
    question_count: int
    # The clarification question awaiting an answer (Phase 2A generates one,
    # Phase 2B moves it into questions_asked/answers once answered). None
    # when there is no pending question.
    current_question: str | None
    current_why: str | None
    # Phase 2D: whether the coaching conversation has been decided complete,
    # and why. False/None while coaching is in progress or continuing.
    is_complete: bool
    stop_reason: str | None
