"""Weakest-criterion selection for Phase 2A.

Deterministic and LLM-free by design, so this can be unit tested directly
without an unnecessary real Claude API call.
"""

from app.analysis.schemas import AnalysisResult

# Fixed priority order used to break ties among equally-low-scoring criteria.
CRITERION_PRIORITY: tuple[str, ...] = (
    "requirement_clarity",
    "acceptance_criteria",
    "open_questions",
    "scope_definition",
)

CRITERION_LABELS: dict[str, str] = {
    "requirement_clarity": "Requirement Clarity",
    "acceptance_criteria": "Acceptance Criteria",
    "open_questions": "Open Questions",
    "scope_definition": "Scope Definition",
}

# Which Phase 1 AnalysisContent fields hold the relevant unresolved-issue
# evidence for each criterion.
_CRITERION_ISSUE_FIELDS: dict[str, tuple[str, ...]] = {
    "requirement_clarity": ("what_is_missing", "what_is_ambiguous", "assumptions"),
    "acceptance_criteria": ("missing_acceptance_criteria",),
    "open_questions": ("important_open_questions",),
    "scope_definition": ("scope_problems",),
}


def select_weakest_criterion(analysis: AnalysisResult) -> str:
    """Return the key of the lowest-scoring criterion.

    Ties are broken by CRITERION_PRIORITY order: `min()` is stable and only
    updates on a strictly lower score, and CRITERION_PRIORITY is already
    listed in the fixed priority order, so the first-listed criterion among
    equal scores wins.
    """
    scores = [(key, getattr(analysis, key).score) for key in CRITERION_PRIORITY]
    return min(scores, key=lambda pair: pair[1])[0]


def gather_relevant_issues(analysis: AnalysisResult, criterion_key: str) -> list[str]:
    """Collect the Phase 1 findings relevant to the given criterion."""
    fields = _CRITERION_ISSUE_FIELDS[criterion_key]
    issues: list[str] = []
    for field in fields:
        issues.extend(getattr(analysis, field))
    return issues
