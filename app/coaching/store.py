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


def create_session(ticket: TicketInput, analysis: AnalysisResult) -> str:
    session_id = str(uuid.uuid4())
    _SESSIONS[session_id] = {
        "ticket": ticket,
        "analysis": analysis,
        "questions_asked": [],
        "answers": [],
        "question_count": 0,
    }
    return session_id


def get_session(session_id: str) -> CoachingSessionState | None:
    return _SESSIONS.get(session_id)
