"""Tests for the Phase 1 single-shot requirement analysis endpoint.

These hit the real Claude API through POST /api/analyse (no mocking),
since Phase 1 is defined as mock ticket -> LangGraph -> Claude -> structured
analysis, and ANTHROPIC_API_KEY is expected to be configured locally.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

VAGUE_TICKET = {
    "title": "Add notification feature",
    "description": "Users should receive notifications when something happens.",
}

CLEAR_TICKET = {
    "title": "Add push notification when a new direct message is received",
    "description": (
        "When a user receives a new direct message, the system must send them "
        "a push notification within 5 seconds.\n\n"
        "Acceptance Criteria:\n"
        "- Given the recipient has push notifications enabled, when a new direct "
        "message arrives, then a push notification is sent within 5 seconds.\n"
        "- Given the recipient has push notifications disabled, when a new direct "
        "message arrives, then no push notification is sent.\n"
        "- The notification includes the sender's name and a preview of the "
        "first 50 characters of the message.\n"
        "- Tapping the notification opens the relevant conversation thread.\n\n"
        "Scope:\n"
        "- Covers direct messages only, not group messages or other notification "
        "types.\n"
        "- Email notifications are explicitly out of scope for this ticket.\n\n"
        "Dependencies:\n"
        "- Requires the existing Notification Service (REQ-101) to be available."
    ),
}

_CRITERIA_FIELDS = (
    "requirement_clarity",
    "acceptance_criteria",
    "open_questions",
    "scope_definition",
)

_LIST_FIELDS = (
    "what_is_clear",
    "what_is_missing",
    "what_is_ambiguous",
    "assumptions",
    "possible_dependencies",
    "scope_problems",
    "missing_acceptance_criteria",
    "important_open_questions",
    "clarification_questions",
)


def _assert_valid_analysis_shape(data: dict) -> None:
    for key in _CRITERIA_FIELDS:
        criterion = data[key]
        assert 0 <= criterion["score"] <= 3
        assert isinstance(criterion["evidence"], str) and criterion["evidence"].strip()

    expected_overall = round(sum(data[key]["score"] for key in _CRITERIA_FIELDS) / 4, 2)
    assert data["overall_readiness"] == pytest.approx(expected_overall)
    assert 0 <= data["overall_readiness"] <= 3

    for list_field in _LIST_FIELDS:
        assert list_field in data
        assert isinstance(data[list_field], list)

    for question in data["clarification_questions"]:
        assert question["question"].strip()
        assert question["reason"].strip()


def test_vague_notification_ticket_scores_low_and_has_gaps():
    response = client.post("/api/analyse", json=VAGUE_TICKET)
    assert response.status_code == 200
    data = response.json()

    _assert_valid_analysis_shape(data)

    # The ticket doesn't say what event triggers the notification, so this
    # should surface as a real gap, not be scored as ready.
    assert len(data["what_is_missing"]) > 0
    assert len(data["clarification_questions"]) > 0
    assert data["overall_readiness"] < 2.0


def test_clear_ticket_scores_higher_than_vague_ticket():
    vague_response = client.post("/api/analyse", json=VAGUE_TICKET)
    clear_response = client.post("/api/analyse", json=CLEAR_TICKET)

    assert vague_response.status_code == 200
    assert clear_response.status_code == 200

    vague_data = vague_response.json()
    clear_data = clear_response.json()

    _assert_valid_analysis_shape(clear_data)

    assert clear_data["overall_readiness"] > vague_data["overall_readiness"]
    assert clear_data["acceptance_criteria"]["score"] >= 2
