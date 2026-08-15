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
    questions_asked: list[dict]
    answers: list[dict]
    question_count: int
