"""In-memory reviewed-ticket history store.

TEMPORARY SCAFFOLDING - NOT SUITABLE FOR PRODUCTION.

Mirrors app/jira/store.py's shape (a process-local store, no auth/user
system yet to scope by - app/auth/ is an empty stub). Survives a frontend
page refresh (the backend process keeps running) but not a backend process
restart, and is not safe across multiple worker processes - same
documented limitation as app/jira/store.py.

A ticket is upserted by issue_key: recorded once right after analysis and
again if the user goes on to finish coaching, so the second call updates
the existing entry (moving it to the front) rather than adding a duplicate
row for the same ticket. Tickets with no issue_key (entered manually, no
source_issue_key) are never deduplicated - each is appended as a new entry.
"""

from app.tickets.schemas import ReviewedTicket

_REVIEWED_TICKETS: list[ReviewedTicket] = []


def upsert_reviewed_ticket(ticket: ReviewedTicket) -> None:
    global _REVIEWED_TICKETS
    if ticket.issue_key:
        _REVIEWED_TICKETS = [t for t in _REVIEWED_TICKETS if t.issue_key != ticket.issue_key]
    _REVIEWED_TICKETS.insert(0, ticket)


def list_reviewed_tickets() -> list[ReviewedTicket]:
    return list(_REVIEWED_TICKETS)
