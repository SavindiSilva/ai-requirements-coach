"""Deterministic coaching stop-condition check for Phase 2D.

Pure and LLM-free by design, mirroring app/coaching/selection.py, so it can
be unit tested directly without a real Claude API call.
"""

from app.analysis.schemas import AnalysisResult
from app.coaching.selection import CRITERION_LABELS, CRITERION_PRIORITY
from app.core.config import settings

MAX_QUESTIONS_REACHED = "max_questions_reached"
READINESS_THRESHOLD_MET = "readiness_threshold_met"


def should_stop_coaching(analysis: AnalysisResult, question_count: int) -> tuple[bool, str | None]:
    """Decide whether the coaching conversation should stop.

    Stops when either:
    1. the minimum of the four criterion scores >= settings.readiness_pass_threshold
       (never overall_readiness alone), or
    2. question_count >= settings.max_clarification_rounds.

    Readiness is checked first so a round that satisfies both conditions at
    once (readiness reached on the same round the question cap is hit) is
    recorded as READINESS_THRESHOLD_MET, not MAX_QUESTIONS_REACHED -
    max_questions_reached should only occur when the cap was hit WITHOUT
    also reaching full readiness.

    Returns (should_stop, stop_reason); stop_reason is None when continuing.
    """
    min_score = min(
        analysis.requirement_clarity.score,
        analysis.acceptance_criteria.score,
        analysis.open_questions.score,
        analysis.scope_definition.score,
    )
    if min_score >= settings.readiness_pass_threshold:
        return True, READINESS_THRESHOLD_MET

    if question_count >= settings.max_clarification_rounds:
        return True, MAX_QUESTIONS_REACHED

    return False, None


def compute_remaining_gaps(analysis: AnalysisResult) -> list[str]:
    """Return the labels of criteria still below settings.readiness_pass_threshold.

    Deterministic and LLM-free, mirroring should_stop_coaching - Claude is
    never asked to judge this. Returns [] when every criterion already meets
    the threshold.
    """
    return [
        CRITERION_LABELS[key]
        for key in CRITERION_PRIORITY
        if getattr(analysis, key).score < settings.readiness_pass_threshold
    ]
