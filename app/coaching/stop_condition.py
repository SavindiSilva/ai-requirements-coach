"""Deterministic coaching stop-condition check for Phase 2D.

Pure and LLM-free by design, mirroring app/coaching/selection.py, so it can
be unit tested directly without a real Claude API call.
"""

from app.analysis.schemas import AnalysisResult
from app.core.config import settings

MAX_QUESTIONS_REACHED = "max_questions_reached"
READINESS_THRESHOLD_MET = "readiness_threshold_met"


def should_stop_coaching(analysis: AnalysisResult, question_count: int) -> tuple[bool, str | None]:
    """Decide whether the coaching conversation should stop.

    Stops when either:
    1. question_count >= settings.max_clarification_rounds, or
    2. the minimum of the four criterion scores >= settings.readiness_pass_threshold
       (never overall_readiness alone).

    Returns (should_stop, stop_reason); stop_reason is None when continuing.
    """
    if question_count >= settings.max_clarification_rounds:
        return True, MAX_QUESTIONS_REACHED

    min_score = min(
        analysis.requirement_clarity.score,
        analysis.acceptance_criteria.score,
        analysis.open_questions.score,
        analysis.scope_definition.score,
    )
    if min_score >= settings.readiness_pass_threshold:
        return True, READINESS_THRESHOLD_MET

    return False, None
