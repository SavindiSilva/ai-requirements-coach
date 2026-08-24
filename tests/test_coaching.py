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
from app.coaching.llm import FINAL_REQUIREMENT_TOOL_NAME, normalize_final_requirement_input
from app.coaching.schemas import ClarificationQuestionOutput, FinalRequirementContent
from app.coaching.selection import select_weakest_criterion
from app.coaching.store import create_session, get_session, record_answer
from app.core.config import settings
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


# --- Phase 2D: decide whether to continue coaching ---
#
# should_stop_coaching is pure and LLM-free (like select_weakest_criterion),
# so the stop/continue decision itself needs no mocking. Every test below
# monkeypatches app.coaching.router.generate_clarification_question so a
# real Claude call only happens when a test is specifically checking the
# continue path's question-generation wiring.


def _create_next_ready_session(analysis: AnalysisResult, question_count: int = 1) -> str:
    """Build a session in the state POST /next expects: an answered round,
    no pending question, consistent history, and the given analysis (as if
    Phase 2C re-analysis had just produced it)."""
    session_id = _create_answered_session()
    session = get_session(session_id)
    session["analysis"] = analysis
    session["question_count"] = question_count
    session["questions_asked"] = [f"Question {i}" for i in range(question_count)]
    session["answers"] = [f"Answer {i}" for i in range(question_count)]
    return session_id


def test_coaching_next_continues_when_below_threshold(monkeypatch):
    analysis = _make_analysis(rc=1, ac=1, oq=0, sd=2)  # min score 0 < threshold 2
    session_id = _create_next_ready_session(analysis, question_count=1)

    def _fake_generate(system_prompt, user_prompt):
        return ClarificationQuestionOutput(
            question="What does 'something happens' mean?",
            why="The triggering event is still undefined.",
        )

    monkeypatch.setattr("app.coaching.router.generate_clarification_question", _fake_generate)

    response = client.post(f"/api/coaching/{session_id}/next")
    assert response.status_code == 200
    data = response.json()

    assert data["session_id"] == session_id
    assert data["is_complete"] is False
    assert data["stop_reason"] is None
    assert data["question"] == "What does 'something happens' mean?"
    assert data["why"] == "The triggering event is still undefined."
    assert data["question_count"] == 1

    session = get_session(session_id)
    assert session["question_count"] == 1
    assert session["questions_asked"] == ["Question 0"]
    assert session["answers"] == ["Answer 0"]
    assert session["current_question"] == "What does 'something happens' mean?"
    assert session["current_why"] == "The triggering event is still undefined."
    assert session["is_complete"] is False
    assert session["stop_reason"] is None


def test_coaching_next_stops_when_readiness_threshold_met(monkeypatch):
    analysis = _make_analysis(rc=2, ac=2, oq=2, sd=2)  # min score 2 >= threshold 2
    session_id = _create_next_ready_session(analysis, question_count=1)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("Claude must not be called when the stop condition is met")

    monkeypatch.setattr("app.coaching.router.generate_clarification_question", _fail_if_called)

    response = client.post(f"/api/coaching/{session_id}/next")
    assert response.status_code == 200
    data = response.json()

    assert data["is_complete"] is True
    assert data["stop_reason"] == "readiness_threshold_met"
    assert data["question"] is None
    assert data["why"] is None

    session = get_session(session_id)
    assert session["is_complete"] is True
    assert session["stop_reason"] == "readiness_threshold_met"
    assert session["current_question"] is None
    assert session["current_why"] is None
    # question_count/questions_asked/answers must be untouched by stopping.
    assert session["question_count"] == 1
    assert session["questions_asked"] == ["Question 0"]
    assert session["answers"] == ["Answer 0"]


def test_coaching_next_stops_when_max_questions_reached(monkeypatch):
    analysis = _make_analysis(rc=0, ac=0, oq=0, sd=0)  # well below readiness threshold
    session_id = _create_next_ready_session(analysis, question_count=settings.max_clarification_rounds)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("Claude must not be called when the stop condition is met")

    monkeypatch.setattr("app.coaching.router.generate_clarification_question", _fail_if_called)

    response = client.post(f"/api/coaching/{session_id}/next")
    assert response.status_code == 200
    data = response.json()

    assert data["is_complete"] is True
    assert data["stop_reason"] == "max_questions_reached"
    assert data["question"] is None
    assert data["why"] is None

    session = get_session(session_id)
    assert session["is_complete"] is True
    assert session["stop_reason"] == "max_questions_reached"
    assert session["question_count"] == settings.max_clarification_rounds


def test_coaching_next_unknown_session_returns_404():
    response = client.post("/api/coaching/nonexistent-session/next")
    assert response.status_code == 404


def test_coaching_next_pending_question_returns_400(monkeypatch):
    session_id = _create_session_directly()  # current_question is set, question_count=0

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("Claude must not be called when there is a pending question")

    monkeypatch.setattr("app.coaching.router.generate_clarification_question", _fail_if_called)

    response = client.post(f"/api/coaching/{session_id}/next")
    assert response.status_code == 400
    assert "answered" in response.json()["detail"].lower()


def test_coaching_next_already_complete_returns_400(monkeypatch):
    analysis = _make_analysis(rc=2, ac=2, oq=2, sd=2)
    session_id = _create_next_ready_session(analysis, question_count=1)
    session = get_session(session_id)
    session["is_complete"] = True
    session["stop_reason"] = "readiness_threshold_met"

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("Claude must not be called when the session is already complete")

    monkeypatch.setattr("app.coaching.router.generate_clarification_question", _fail_if_called)

    response = client.post(f"/api/coaching/{session_id}/next")
    assert response.status_code == 400
    assert "already complete" in response.json()["detail"].lower()


def test_coaching_next_inconsistent_history_returns_400(monkeypatch):
    analysis = _make_analysis(rc=1, ac=1, oq=0, sd=2)
    session_id = _create_next_ready_session(analysis, question_count=1)
    session = get_session(session_id)
    session["questions_asked"] = ["Question 1", "Question 2"]
    session["answers"] = ["Answer 1"]

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("Claude must not be called when history is inconsistent")

    monkeypatch.setattr("app.coaching.router.generate_clarification_question", _fail_if_called)

    response = client.post(f"/api/coaching/{session_id}/next")
    assert response.status_code == 400
    assert "inconsist" in response.json()["detail"].lower()

    session_after = get_session(session_id)
    assert session_after["is_complete"] is False
    assert session_after["questions_asked"] == ["Question 1", "Question 2"]
    assert session_after["answers"] == ["Answer 1"]


def test_coaching_next_passes_previous_questions_to_prompt(monkeypatch):
    analysis = _make_analysis(rc=1, ac=1, oq=0, sd=2)
    session_id = _create_next_ready_session(analysis, question_count=1)
    session = get_session(session_id)
    session["questions_asked"] = ["What event should trigger the notification?"]
    session["answers"] = ["When a new message is received."]

    captured: dict = {}

    def _spy_build_user_prompt(ticket, analysis, criterion_key, issues, previous_questions=None):
        captured["previous_questions"] = previous_questions
        return "irrelevant prompt text"

    def _fake_generate(system_prompt, user_prompt):
        return ClarificationQuestionOutput(question="Next question?", why="Next reason.")

    monkeypatch.setattr("app.coaching.router.build_question_user_prompt", _spy_build_user_prompt)
    monkeypatch.setattr("app.coaching.router.generate_clarification_question", _fake_generate)

    response = client.post(f"/api/coaching/{session_id}/next")
    assert response.status_code == 200
    assert captured["previous_questions"] == ["What event should trigger the notification?"]


# --- Phase 2E: generate the final development-ready requirement ---
#
# generate_final_requirement is the only Claude call in this step; every
# test below monkeypatches app.coaching.router.generate_final_requirement
# so no real API call happens except in a manual verification pass.


def _create_completed_session(
    analysis: AnalysisResult,
    stop_reason: str,
    question_count: int = 1,
) -> str:
    """Build a session in the state POST /finalize expects: coaching marked
    complete with the given analysis and stop_reason."""
    session_id = _create_next_ready_session(analysis, question_count=question_count)
    session = get_session(session_id)
    session["is_complete"] = True
    session["stop_reason"] = stop_reason
    session["current_question"] = None
    session["current_why"] = None
    return session_id


_SAMPLE_FINAL_REQUIREMENT = FinalRequirementContent(
    user_story="As a message recipient, I want to be notified when I receive a new message so I can respond promptly.",
    acceptance_criteria=[
        "Given User A sends a message to User B, when the message is sent, then User B receives a notification.",
        "Given User A sends a message to User B, when the message is sent, then User A does not receive a notification.",
    ],
    scope=["Notification triggered only by new-message receipt."],
    assumptions=["An existing messaging feature already generates 'new message' events."],
    dependencies=["Likely depends on the existing messaging feature that generates message-received events."],
)


def test_coaching_finalize_readiness_threshold_met(monkeypatch):
    analysis = _make_analysis(rc=2, ac=2, oq=2, sd=2)  # all >= threshold 2
    session_id = _create_completed_session(analysis, "readiness_threshold_met", question_count=1)
    original_session = get_session(session_id)
    original_questions_asked = list(original_session["questions_asked"])
    original_answers = list(original_session["answers"])

    call_count = {"n": 0}

    def _fake_generate(system_prompt, user_prompt, **kwargs):
        call_count["n"] += 1
        return _SAMPLE_FINAL_REQUIREMENT

    monkeypatch.setattr("app.coaching.router.generate_final_requirement", _fake_generate)

    response = client.post(f"/api/coaching/{session_id}/finalize")
    assert response.status_code == 200
    data = response.json()

    assert data["session_id"] == session_id
    assert data["is_complete"] is True
    assert data["stop_reason"] == "readiness_threshold_met"
    assert data["remaining_gaps"] == []
    assert data["final_requirement"]["user_story"] == _SAMPLE_FINAL_REQUIREMENT.user_story
    assert data["final_requirement"]["acceptance_criteria"] == _SAMPLE_FINAL_REQUIREMENT.acceptance_criteria
    assert call_count["n"] == 1

    session = get_session(session_id)
    assert session["final_requirement"] == _SAMPLE_FINAL_REQUIREMENT
    assert session["questions_asked"] == original_questions_asked
    assert session["answers"] == original_answers
    assert session["question_count"] == 1
    assert session["analysis"] is analysis


def test_coaching_finalize_max_questions_reached_with_remaining_gaps(monkeypatch):
    # rc=2, ac=0, oq=2, sd=1 with threshold=2 -> gaps in Acceptance Criteria
    # and Scope Definition, matching the worked example from the spec.
    analysis = _make_analysis(rc=2, ac=0, oq=2, sd=1)
    session_id = _create_completed_session(analysis, "max_questions_reached", question_count=5)

    def _fake_generate(system_prompt, user_prompt, **kwargs):
        return _SAMPLE_FINAL_REQUIREMENT

    monkeypatch.setattr("app.coaching.router.generate_final_requirement", _fake_generate)

    response = client.post(f"/api/coaching/{session_id}/finalize")
    assert response.status_code == 200
    data = response.json()

    assert data["stop_reason"] == "max_questions_reached"
    assert data["remaining_gaps"] == ["Acceptance Criteria", "Scope Definition"]
    assert data["final_requirement"]["user_story"]


def test_coaching_finalize_unknown_session_returns_404(monkeypatch):
    def _fail_if_called(*args, **kwargs):
        raise AssertionError("Claude must not be called for an unknown session")

    monkeypatch.setattr("app.coaching.router.generate_final_requirement", _fail_if_called)

    response = client.post("/api/coaching/nonexistent-session/finalize")
    assert response.status_code == 404


def test_coaching_finalize_coaching_not_complete_returns_400(monkeypatch):
    analysis = _make_analysis(rc=1, ac=1, oq=0, sd=2)
    session_id = _create_next_ready_session(analysis, question_count=1)  # is_complete stays False

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("Claude must not be called when coaching is not complete")

    monkeypatch.setattr("app.coaching.router.generate_final_requirement", _fail_if_called)

    response = client.post(f"/api/coaching/{session_id}/finalize")
    assert response.status_code == 400
    assert "not complete" in response.json()["detail"].lower()


def test_coaching_finalize_inconsistent_history_returns_400(monkeypatch):
    analysis = _make_analysis(rc=2, ac=2, oq=2, sd=2)
    session_id = _create_completed_session(analysis, "readiness_threshold_met", question_count=1)
    session = get_session(session_id)
    session["questions_asked"] = ["Question 1", "Question 2"]
    session["answers"] = ["Answer 1"]

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("Claude must not be called when history is inconsistent")

    monkeypatch.setattr("app.coaching.router.generate_final_requirement", _fail_if_called)

    response = client.post(f"/api/coaching/{session_id}/finalize")
    assert response.status_code == 400
    assert "inconsist" in response.json()["detail"].lower()

    session_after = get_session(session_id)
    assert session_after["final_requirement"] is None


def test_coaching_finalize_returns_cached_result_without_calling_claude(monkeypatch):
    analysis = _make_analysis(rc=2, ac=2, oq=2, sd=2)
    session_id = _create_completed_session(analysis, "readiness_threshold_met", question_count=1)
    session = get_session(session_id)
    session["final_requirement"] = _SAMPLE_FINAL_REQUIREMENT

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("Claude must not be called when a final requirement already exists")

    monkeypatch.setattr("app.coaching.router.generate_final_requirement", _fail_if_called)

    response = client.post(f"/api/coaching/{session_id}/finalize")
    assert response.status_code == 200
    data = response.json()

    assert data["final_requirement"]["user_story"] == _SAMPLE_FINAL_REQUIREMENT.user_story
    assert data["final_requirement"]["dependencies"] == _SAMPLE_FINAL_REQUIREMENT.dependencies


def test_coaching_finalize_prompt_receives_complete_context(monkeypatch):
    analysis = _make_analysis(rc=2, ac=0, oq=2, sd=1)
    session_id = _create_completed_session(analysis, "max_questions_reached", question_count=1)
    session = get_session(session_id)
    session["questions_asked"] = ["What event should trigger the notification?"]
    session["answers"] = ["When a new message is received."]

    captured: dict = {}

    def _spy_build_user_prompt(ticket, analysis, coaching_history, stop_reason, retrieved_context=None):
        captured["ticket"] = ticket
        captured["analysis"] = analysis
        captured["coaching_history"] = coaching_history
        captured["stop_reason"] = stop_reason
        return "irrelevant prompt text"

    def _fake_generate(system_prompt, user_prompt, **kwargs):
        return _SAMPLE_FINAL_REQUIREMENT

    monkeypatch.setattr("app.coaching.router.build_finalize_user_prompt", _spy_build_user_prompt)
    monkeypatch.setattr("app.coaching.router.generate_final_requirement", _fake_generate)

    response = client.post(f"/api/coaching/{session_id}/finalize")
    assert response.status_code == 200

    assert captured["ticket"] == session["ticket"]
    assert captured["analysis"] is analysis
    assert captured["coaching_history"] == [
        ("What event should trigger the notification?", "When a new message is received.")
    ]
    assert captured["stop_reason"] == "max_questions_reached"


def test_coaching_finalize_structured_output_matches_schema(monkeypatch):
    analysis = _make_analysis(rc=2, ac=2, oq=2, sd=2)
    session_id = _create_completed_session(analysis, "readiness_threshold_met", question_count=1)

    mocked_output = FinalRequirementContent(
        user_story="As a recipient, I want a notification when a new message arrives so I notice it promptly.",
        acceptance_criteria=["Given a new message is sent, when it arrives, then the recipient is notified."],
        scope=["New-message notifications only."],
        assumptions=[],
        dependencies=[],
    )

    def _fake_generate(system_prompt, user_prompt, **kwargs):
        return mocked_output

    monkeypatch.setattr("app.coaching.router.generate_final_requirement", _fake_generate)

    response = client.post(f"/api/coaching/{session_id}/finalize")
    assert response.status_code == 200
    data = response.json()

    assert data["final_requirement"] == {
        "user_story": mocked_output.user_story,
        "acceptance_criteria": mocked_output.acceptance_criteria,
        "scope": mocked_output.scope,
        "assumptions": mocked_output.assumptions,
        "dependencies": mocked_output.dependencies,
    }
    session = get_session(session_id)
    assert session["final_requirement"] == mocked_output


# --- Phase 2E robustness: normalize_final_requirement_input coercion ---
#
# Claude occasionally returns a malformed submit_final_requirement call for a
# genuinely under-informative coaching outcome (max_questions_reached with
# consistently vague answers) - observed in production as a list-typed field
# collapsed into a single string, with user_story omitted entirely.
# normalize_final_requirement_input() is pure and LLM-free, so it's tested
# directly here with hand-built malformed dicts, no real Claude call needed -
# same convention as select_weakest_criterion/should_stop_coaching.


def test_normalize_final_requirement_input_wraps_string_list_field(caplog):
    raw = {
        "user_story": "As a user, I want X so that Y.",
        "acceptance_criteria": "Given a Jira issue is created, when ..., then ...",
        "scope": [],
        "assumptions": [],
        "dependencies": [],
    }

    with caplog.at_level("WARNING"):
        result = normalize_final_requirement_input(
            raw, ticket_title="Add Slack notifications", session_id="sess-1"
        )

    assert result["acceptance_criteria"] == ["Given a Jira issue is created, when ..., then ..."]
    assert result["user_story"] == raw["user_story"]  # untouched, already valid
    assert any(
        "acceptance_criteria" in r.message and "sess-1" in r.message for r in caplog.records
    )


def test_normalize_final_requirement_input_synthesizes_missing_user_story(caplog):
    raw = {
        "acceptance_criteria": ["Some criterion."],
        "scope": [],
        "assumptions": [],
        "dependencies": [],
    }

    with caplog.at_level("WARNING"):
        result = normalize_final_requirement_input(
            raw, ticket_title="Add Slack notifications", session_id="sess-2"
        )

    assert "Add Slack notifications" in result["user_story"]
    assert result["acceptance_criteria"] == ["Some criterion."]  # untouched, already a list
    assert any("user_story" in r.message and "sess-2" in r.message for r in caplog.records)


def test_normalize_final_requirement_input_synthesizes_blank_user_story():
    raw = {"user_story": "   ", "acceptance_criteria": []}
    result = normalize_final_requirement_input(raw, ticket_title="Fix the thing", session_id="sess-3")
    assert result["user_story"] != "   "
    assert "Fix the thing" in result["user_story"]


def test_normalize_final_requirement_input_recovers_both_malformed_fields_at_once(caplog):
    # Mirrors the actual production failure: only acceptance_criteria
    # present, as a string, and user_story entirely absent from the dict.
    raw = {"acceptance_criteria": "Given a Jira issue is successfully created, ...(truncated)"}

    with caplog.at_level("WARNING"):
        result = normalize_final_requirement_input(
            raw, ticket_title="Add Slack notifications", session_id="sess-4"
        )

    normalized = FinalRequirementContent.model_validate(result)
    assert normalized.acceptance_criteria == ["Given a Jira issue is successfully created, ...(truncated)"]
    assert normalized.scope == []
    assert normalized.assumptions == []
    assert normalized.dependencies == []
    assert "Add Slack notifications" in normalized.user_story
    warnings = [r.message for r in caplog.records]
    assert any("acceptance_criteria" in w for w in warnings)
    assert any("user_story" in w for w in warnings)


def test_normalize_final_requirement_input_leaves_valid_input_untouched(caplog):
    raw = {
        "user_story": "As a user, I want X so that Y.",
        "acceptance_criteria": ["Criterion 1."],
        "scope": ["In scope."],
        "assumptions": ["Assumption."],
        "dependencies": ["Dependency."],
    }

    with caplog.at_level("WARNING"):
        result = normalize_final_requirement_input(raw, ticket_title="irrelevant", session_id="sess-5")

    assert result == raw
    assert caplog.records == []


def test_normalize_final_requirement_input_does_not_coerce_empty_string_list_field():
    # An empty string isn't recoverable content - leave it as-is so Pydantic
    # rejects it normally rather than silently inventing a [""] item.
    raw = {"user_story": "As a user, I want X so that Y.", "acceptance_criteria": ""}
    result = normalize_final_requirement_input(raw, ticket_title="irrelevant", session_id="sess-6")
    assert result["acceptance_criteria"] == ""


# --- Phase 2E robustness: end-to-end recovery from a malformed Claude response ---
#
# generate_final_requirement itself is exercised here (not monkeypatched) by
# faking the underlying Anthropic client, reproducing the exact malformed
# shape captured from the real production failure - confirms /finalize
# returns 200 with a coerced result instead of 502, and that the coercion is
# logged.


class _FakeToolUseBlock:
    def __init__(self, name: str, input_: dict):
        self.type = "tool_use"
        self.name = name
        self.input = input_


class _FakeMessagesResponse:
    def __init__(self, content: list):
        self.content = content


class _FakeMessages:
    def __init__(self, content: list):
        self._content = content

    def create(self, **kwargs):
        return _FakeMessagesResponse(self._content)


class _FakeAnthropicClient:
    def __init__(self, content: list):
        self.messages = _FakeMessages(content)


def test_coaching_finalize_recovers_from_malformed_claude_response(monkeypatch, caplog):
    analysis = _make_analysis(rc=1, ac=0, oq=0, sd=0)
    session_id = _create_completed_session(analysis, "max_questions_reached", question_count=5)

    malformed_input = {
        "acceptance_criteria": (
            "Given a Jira issue is successfully created, when the app attempts to notify "
            "Slack, the message content and channel are undetermined (truncated for this test)."
        )
    }
    fake_client = _FakeAnthropicClient([_FakeToolUseBlock(FINAL_REQUIREMENT_TOOL_NAME, malformed_input)])
    monkeypatch.setattr("app.coaching.llm.get_client", lambda: fake_client)

    with caplog.at_level("WARNING"):
        response = client.post(f"/api/coaching/{session_id}/finalize")

    assert response.status_code == 200
    data = response.json()
    assert data["final_requirement"]["acceptance_criteria"] == [malformed_input["acceptance_criteria"]]
    assert data["final_requirement"]["scope"] == []
    assert data["final_requirement"]["assumptions"] == []
    assert data["final_requirement"]["dependencies"] == []
    assert data["final_requirement"]["user_story"]  # non-empty fallback

    warnings = [r.message for r in caplog.records]
    assert any("acceptance_criteria" in w and session_id in w for w in warnings)
    assert any("user_story" in w and session_id in w for w in warnings)
