"""Tests for the Phase 2A coaching-start endpoint.

The criterion-selection logic (select_weakest_criterion) is pure and
LLM-free, so tie-breaking is tested directly against constructed
AnalysisResult objects — no real Claude API call needed for that.

The full-endpoint test hits the real Claude API through
POST /api/coaching/start (no mocking), matching the convention already used
in tests/test_analysis.py.
"""

from app.analysis.schemas import AnalysisResult, CriterionScore
from app.coaching.selection import select_weakest_criterion
from app.coaching.store import get_session
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

VAGUE_TICKET = {
    "title": "Add notification feature",
    "description": "Users should receive notifications when something happens.",
}


def _make_analysis(rc: int, ac: int, oq: int, sd: int) -> AnalysisResult:
    return AnalysisResult(
        requirement_clarity=CriterionScore(score=rc, evidence="evidence"),
        acceptance_criteria=CriterionScore(score=ac, evidence="evidence"),
        open_questions=CriterionScore(score=oq, evidence="evidence"),
        scope_definition=CriterionScore(score=sd, evidence="evidence"),
        overall_readiness=round((rc + ac + oq + sd) / 4, 2),
    )


def test_weakest_criterion_no_tie_selects_true_lowest():
    analysis = _make_analysis(rc=2, ac=0, oq=2, sd=3)
    assert select_weakest_criterion(analysis) == "acceptance_criteria"


def test_weakest_criterion_tie_break_prefers_requirement_clarity():
    # Requirement Clarity and Acceptance Criteria tie at the lowest score (1).
    # Fixed priority order (Requirement Clarity > Acceptance Criteria >
    # Open Questions > Scope Definition) says Requirement Clarity wins.
    analysis = _make_analysis(rc=1, ac=1, oq=2, sd=3)
    assert select_weakest_criterion(analysis) == "requirement_clarity"


def test_weakest_criterion_tie_break_prefers_acceptance_criteria_over_open_questions():
    analysis = _make_analysis(rc=3, ac=1, oq=1, sd=2)
    assert select_weakest_criterion(analysis) == "acceptance_criteria"


def test_coaching_start_returns_question_and_stores_session():
    response = client.post("/api/coaching/start", json=VAGUE_TICKET)
    assert response.status_code == 200
    data = response.json()

    assert data["session_id"]
    assert data["question"].strip()
    assert data["why"].strip()

    scores = data["current_scores"]
    for key in ("requirement_clarity", "acceptance_criteria", "open_questions", "scope_definition"):
        assert 0 <= scores[key] <= 3

    session = get_session(data["session_id"])
    assert session is not None
    assert session["ticket"].title == VAGUE_TICKET["title"]
    assert session["question_count"] == 0
    assert session["questions_asked"] == []
    assert session["answers"] == []

    # The question must target the actual weakest criterion of the analysis
    # that was stored for this session (not just any criterion).
    analysis = session["analysis"]
    weakest_key = select_weakest_criterion(analysis)
    all_scores = [
        analysis.requirement_clarity.score,
        analysis.acceptance_criteria.score,
        analysis.open_questions.score,
        analysis.scope_definition.score,
    ]
    assert getattr(analysis, weakest_key).score == min(all_scores)
    assert data["current_scores"][weakest_key] == getattr(analysis, weakest_key).score
