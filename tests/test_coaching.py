"""Tests for the Phase 2A coaching-start and Phase 2B coaching-message endpoints.

The criterion-selection logic (select_weakest_criterion) is pure and
LLM-free, so tie-breaking is tested directly against constructed
AnalysisResult objects — no real Claude API call needed for that.

The Phase 2A full-endpoint test hits the real Claude API through
POST /api/coaching/start (no mocking), matching the convention already used
in tests/test_analysis.py. Phase 2B is pure in-memory state mutation (it
never calls Claude), so most of its tests build a session directly via
app.coaching.store.create_session instead of paying for a real Phase 2A
call; only the "successful answer submission" test follows the full
start -> message flow, as required by the Phase 2B spec.
"""

from app.agent.llm import LLMAnalysisError
from app.analysis.schemas import AnalysisResult, CriterionScore, TicketInput
from app.coaching.selection import select_weakest_criterion
from app.coaching.store import create_session, get_session, record_answer
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


def _create_session_directly(
    question: str = "What specific event should trigger a notification?",
    why: str = "The ticket does not define the trigger event.",
) -> str:
    ticket = TicketInput(**VAGUE_TICKET)
    analysis = _make_analysis(rc=0, ac=1, oq=0, sd=2)
    return create_session(ticket, analysis, question, why)


def test_coaching_message_successful_answer_submission():
    start_response = client.post("/api/coaching/start", json=VAGUE_TICKET)
    assert start_response.status_code == 200
    start_data = start_response.json()

    session_id = start_data["session_id"]
    question = start_data["question"]
    answer = "When a new message is received."

    message_response = client.post(f"/api/coaching/{session_id}/message", json={"answer": answer})
    assert message_response.status_code == 200
    data = message_response.json()

    assert data["session_id"] == session_id
    assert data["question"] == question
    assert data["answer"] == answer
    assert data["question_count"] == 1
    assert data["questions_asked"] == [question]
    assert data["answers"] == [answer]
    assert len(data["questions_asked"]) == len(data["answers"])

    session = get_session(session_id)
    assert session is not None
    assert session["question_count"] == 1
    assert session["questions_asked"] == [question]
    assert session["answers"] == [answer]
    assert session["current_question"] is None


def test_coaching_message_unknown_session_returns_404():
    response = client.post(
        "/api/coaching/nonexistent-session/message",
        json={"answer": "When a new message is received."},
    )
    assert response.status_code == 404


def test_coaching_message_empty_answer_rejected():
    session_id = _create_session_directly()

    response = client.post(f"/api/coaching/{session_id}/message", json={"answer": ""})
    assert response.status_code == 422

    session = get_session(session_id)
    assert session["question_count"] == 0
    assert session["questions_asked"] == []
    assert session["answers"] == []


def test_coaching_message_whitespace_only_answer_rejected():
    session_id = _create_session_directly()

    response = client.post(f"/api/coaching/{session_id}/message", json={"answer": "   \n\t  "})
    assert response.status_code == 422

    session = get_session(session_id)
    assert session["question_count"] == 0


def test_coaching_message_no_unanswered_question_returns_400():
    session_id = _create_session_directly()

    first = client.post(f"/api/coaching/{session_id}/message", json={"answer": "When a new message is received."})
    assert first.status_code == 200

    second = client.post(f"/api/coaching/{session_id}/message", json={"answer": "Some other answer."})
    assert second.status_code == 400
    assert "no unanswered" in second.json()["detail"].lower()

    # The failed second attempt must not have mutated session state.
    session = get_session(session_id)
    assert session["question_count"] == 1
    assert session["questions_asked"] == ["What specific event should trigger a notification?"]
    assert session["answers"] == ["When a new message is received."]


# --- Phase 2C: re-analysis ---
#
# Re-analysis is pure state mutation plus one Claude call, so all error/
# validation paths below monkeypatch app.coaching.router.analyze_ticket to
# prove Claude is never invoked, instead of spending a real API call per
# case. Only the success test makes a real call, as the Phase 2C spec
# allows for verifying the integration end to end.


def _create_answered_session(
    question: str = "What specific event should trigger a notification?",
    answer: str = "When a new message is received.",
) -> str:
    ticket = TicketInput(**VAGUE_TICKET)
    analysis = _make_analysis(rc=0, ac=1, oq=0, sd=2)
    session_id = create_session(ticket, analysis, question, "The trigger event is undefined.")
    record_answer(session_id, answer)
    return session_id


def test_coaching_reanalyze_successful_reanalysis():
    question = "What specific event should trigger a notification?"
    answer = "When a new message is received."
    session_id = _create_answered_session(question=question, answer=answer)
    original_ticket = get_session(session_id)["ticket"]

    response = client.post(f"/api/coaching/{session_id}/reanalyze")
    assert response.status_code == 200
    data = response.json()

    assert data["session_id"] == session_id

    analysis = data["analysis"]
    for key in ("requirement_clarity", "acceptance_criteria", "open_questions", "scope_definition"):
        assert 0 <= analysis[key]["score"] <= 3
        assert analysis[key]["evidence"].strip()
    assert 0 <= analysis["overall_readiness"] <= 3

    assert data["question_count"] == 1
    assert data["questions_asked"] == [question]
    assert data["answers"] == [answer]

    session = get_session(session_id)
    assert session["ticket"] == original_ticket
    assert session["question_count"] == 1
    assert session["questions_asked"] == [question]
    assert session["answers"] == [answer]
    assert session["current_question"] is None
    assert session["current_why"] is None


def test_coaching_reanalyze_unknown_session_returns_404():
    response = client.post("/api/coaching/nonexistent-session/reanalyze")
    assert response.status_code == 404
    assert get_session("nonexistent-session") is None


def test_coaching_reanalyze_no_answered_questions_returns_400(monkeypatch):
    session_id = _create_session_directly()  # question_count=0, no answers yet
    original_analysis = get_session(session_id)["analysis"]

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("Claude must not be called when there is nothing to re-analyse")

    monkeypatch.setattr("app.coaching.router.analyze_ticket", _fail_if_called)

    response = client.post(f"/api/coaching/{session_id}/reanalyze")
    assert response.status_code == 400
    assert "answered" in response.json()["detail"].lower()

    session = get_session(session_id)
    assert session["analysis"] is original_analysis
    assert session["question_count"] == 0
    assert session["questions_asked"] == []
    assert session["answers"] == []


def test_coaching_reanalyze_inconsistent_history_returns_400(monkeypatch):
    # Both lists non-empty but mismatched in length: this must be reported
    # as "inconsistent history", not "no answered questions" (that rule
    # only fires when questions_asked or answers is empty - see the "no
    # answered questions" test above for that case).
    session_id = _create_session_directly()
    session = get_session(session_id)
    session["questions_asked"] = ["Question 1", "Question 2"]
    session["answers"] = ["Answer 1"]
    session["question_count"] = 2
    original_analysis = session["analysis"]

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("Claude must not be called when history is inconsistent")

    monkeypatch.setattr("app.coaching.router.analyze_ticket", _fail_if_called)

    response = client.post(f"/api/coaching/{session_id}/reanalyze")
    assert response.status_code == 400
    assert "inconsist" in response.json()["detail"].lower()

    session_after = get_session(session_id)
    assert session_after["analysis"] is original_analysis
    assert session_after["questions_asked"] == ["Question 1", "Question 2"]
    assert session_after["answers"] == ["Answer 1"]
    assert session_after["question_count"] == 2


def test_coaching_reanalyze_claude_failure_returns_502_and_preserves_state(monkeypatch):
    session_id = _create_answered_session()
    session = get_session(session_id)
    original_analysis = session["analysis"]
    original_questions_asked = list(session["questions_asked"])
    original_answers = list(session["answers"])
    original_question_count = session["question_count"]

    def _raise(*args, **kwargs):
        raise LLMAnalysisError("simulated Claude failure")

    monkeypatch.setattr("app.coaching.router.analyze_ticket", _raise)

    response = client.post(f"/api/coaching/{session_id}/reanalyze")
    assert response.status_code == 502

    session_after = get_session(session_id)
    assert session_after["analysis"] is original_analysis
    assert session_after["questions_asked"] == original_questions_asked
    assert session_after["answers"] == original_answers
    assert session_after["question_count"] == original_question_count
