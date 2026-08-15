"""In-memory coaching session store (Phase 2A).

TODO(Phase 2B / persistence): replace this process-local dict with a real
database-backed session store once multi-turn coaching and persistence are
implemented (see CLAUDE.md section 21). This does not survive process
restarts and is not safe across multiple worker processes.
"""

import uuid

from app.analysis.schemas import AnalysisResult, TicketInput
from app.coaching.state import CoachingSessionState

_SESSIONS: dict[str, CoachingSessionState] = {}


class SessionNotFoundError(Exception):
    """Raised when a session_id does not exist in the in-memory store."""


class NoUnansweredQuestionError(Exception):
    """Raised when a session has no pending clarification question to answer."""


class NoAnsweredQuestionsError(Exception):
    """Raised when re-analysis is requested but no question has been answered yet."""


class InconsistentHistoryError(Exception):
    """Raised when questions_asked and answers have mismatched lengths."""


def create_session(
    ticket: TicketInput,
    analysis: AnalysisResult,
    question: str,
    why: str,
) -> str:
    session_id = str(uuid.uuid4())
    _SESSIONS[session_id] = {
        "ticket": ticket,
        "analysis": analysis,
        "questions_asked": [],
        "answers": [],
        "question_count": 0,
        "current_question": question,
        "current_why": why,
    }
    return session_id


def get_session(session_id: str) -> CoachingSessionState | None:
    return _SESSIONS.get(session_id)


def record_answer(session_id: str, answer: str) -> CoachingSessionState:
    """Store the user's answer to the session's current pending question.

    Moves `current_question` into `questions_asked`/`answers`, increments
    `question_count`, and clears the pending question. Raises without
    mutating state if the session doesn't exist or has no pending question.
    """
    session = _SESSIONS.get(session_id)
    if session is None:
        raise SessionNotFoundError(f"No coaching session found for session_id '{session_id}'.")

    if session["current_question"] is None:
        raise NoUnansweredQuestionError(
            f"There is no unanswered coaching question for session '{session_id}'."
        )

    session["questions_asked"].append(session["current_question"])
    session["answers"].append(answer)
    session["question_count"] += 1
    session["current_question"] = None
    session["current_why"] = None

    return session


def get_session_for_reanalysis(session_id: str) -> CoachingSessionState:
    """Validate and return a session ready for re-analysis (Phase 2C).

    Raises without mutating anything if the session doesn't exist, has no
    answered question yet, or its question/answer history is inconsistent.
    """
    session = _SESSIONS.get(session_id)
    if session is None:
        raise SessionNotFoundError(f"No coaching session found for session_id '{session_id}'.")

    if session["question_count"] == 0 or not session["questions_asked"] or not session["answers"]:
        raise NoAnsweredQuestionsError(
            f"There is no answered coaching question available for re-analysis in session '{session_id}'."
        )

    if len(session["questions_asked"]) != len(session["answers"]):
        raise InconsistentHistoryError(
            f"Coaching history is inconsistent for session '{session_id}': "
            f"{len(session['questions_asked'])} question(s) but {len(session['answers'])} answer(s)."
        )

    return session


def replace_analysis(session_id: str, analysis: AnalysisResult) -> CoachingSessionState:
    """Replace a session's analysis in place, leaving all other fields untouched."""
    session = _SESSIONS[session_id]
    session["analysis"] = analysis
    return session
