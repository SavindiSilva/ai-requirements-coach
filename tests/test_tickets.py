"""Tests for the reviewed-ticket history (app/tickets/).

Follows the same conventions as tests/test_jira.py for its in-memory
store: a fixture resets the process-local list before/after every test
(this module-level state would otherwise leak between tests), and endpoint
tests use FastAPI's TestClient against the real app.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.tickets import store
from app.tickets.schemas import ReviewedTicket

client_app = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_tickets_store():
    store._REVIEWED_TICKETS.clear()
    yield
    store._REVIEWED_TICKETS.clear()


def _make_ticket(issue_key: str | None = "PROJ-1", **overrides) -> ReviewedTicket:
    defaults = dict(
        issue_key=issue_key,
        title="Add notification feature",
        readiness=1.5,
        reviewed_at=1000.0,
        stop_reason=None,
    )
    defaults.update(overrides)
    return ReviewedTicket(**defaults)


# --- app/tickets/store.py: upsert_reviewed_ticket / list_reviewed_tickets --


def test_list_reviewed_tickets_empty_by_default():
    assert store.list_reviewed_tickets() == []


def test_upsert_reviewed_ticket_adds_new_entry():
    store.upsert_reviewed_ticket(_make_ticket())

    tickets = store.list_reviewed_tickets()
    assert len(tickets) == 1
    assert tickets[0].issue_key == "PROJ-1"


def test_upsert_reviewed_ticket_with_same_issue_key_replaces_not_duplicates():
    store.upsert_reviewed_ticket(_make_ticket(stop_reason=None, reviewed_at=1000.0))
    store.upsert_reviewed_ticket(_make_ticket(stop_reason="readiness_threshold_met", reviewed_at=2000.0))

    tickets = store.list_reviewed_tickets()
    assert len(tickets) == 1
    assert tickets[0].stop_reason == "readiness_threshold_met"
    assert tickets[0].reviewed_at == 2000.0


def test_upsert_reviewed_ticket_moves_updated_entry_to_front():
    store.upsert_reviewed_ticket(_make_ticket(issue_key="PROJ-1", title="First"))
    store.upsert_reviewed_ticket(_make_ticket(issue_key="PROJ-2", title="Second"))
    store.upsert_reviewed_ticket(_make_ticket(issue_key="PROJ-1", title="First (updated)"))

    titles = [t.title for t in store.list_reviewed_tickets()]
    assert titles == ["First (updated)", "Second"]


def test_upsert_reviewed_ticket_without_issue_key_never_deduplicates():
    store.upsert_reviewed_ticket(_make_ticket(issue_key=None, title="Manual ticket"))
    store.upsert_reviewed_ticket(_make_ticket(issue_key=None, title="Manual ticket"))

    assert len(store.list_reviewed_tickets()) == 2


def test_list_reviewed_tickets_most_recently_upserted_first():
    store.upsert_reviewed_ticket(_make_ticket(issue_key="PROJ-1"))
    store.upsert_reviewed_ticket(_make_ticket(issue_key="PROJ-2"))

    tickets = store.list_reviewed_tickets()
    assert [t.issue_key for t in tickets] == ["PROJ-2", "PROJ-1"]


# --- POST /api/tickets/reviewed -------------------------------------------


def test_record_reviewed_ticket_returns_the_recorded_ticket():
    response = client_app.post(
        "/api/tickets/reviewed",
        json={
            "issue_key": "PROJ-9",
            "title": "Add notification feature",
            "readiness": 2.25,
            "reviewed_at": 12345.0,
            "stop_reason": None,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "issue_key": "PROJ-9",
        "title": "Add notification feature",
        "readiness": 2.25,
        "reviewed_at": 12345.0,
        "stop_reason": None,
    }


def test_record_reviewed_ticket_persists_to_the_store():
    client_app.post(
        "/api/tickets/reviewed",
        json={"title": "Manual ticket", "readiness": 1.0, "reviewed_at": 1.0},
    )

    assert len(store.list_reviewed_tickets()) == 1


def test_record_reviewed_ticket_requires_a_title():
    response = client_app.post(
        "/api/tickets/reviewed",
        json={"title": "", "readiness": 1.0, "reviewed_at": 1.0},
    )
    assert response.status_code == 422


def test_record_reviewed_ticket_rejects_readiness_out_of_range():
    response = client_app.post(
        "/api/tickets/reviewed",
        json={"title": "Ticket", "readiness": 3.5, "reviewed_at": 1.0},
    )
    assert response.status_code == 422


# --- GET /api/tickets/reviewed --------------------------------------------


def test_get_reviewed_tickets_returns_empty_list_by_default():
    response = client_app.get("/api/tickets/reviewed")
    assert response.status_code == 200
    assert response.json() == []


def test_get_reviewed_tickets_reflects_recorded_tickets():
    client_app.post(
        "/api/tickets/reviewed",
        json={"issue_key": "PROJ-1", "title": "First", "readiness": 1.0, "reviewed_at": 1.0},
    )
    client_app.post(
        "/api/tickets/reviewed",
        json={"issue_key": "PROJ-2", "title": "Second", "readiness": 2.0, "reviewed_at": 2.0},
    )

    response = client_app.get("/api/tickets/reviewed")

    assert response.status_code == 200
    titles = [t["title"] for t in response.json()]
    assert titles == ["Second", "First"]
