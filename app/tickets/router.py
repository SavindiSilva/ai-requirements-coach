"""FastAPI routes for the reviewed-ticket history.

Additive slice: the frontend records a ticket at the same two points it
previously only updated local React state - right after analysis
(frontend/src/routes/ReviewTicketPage.tsx) and again once coaching
finishes (frontend/src/routes/CoachingPage.tsx) - and Dashboard/History
fetch the list back on mount instead of receiving it as a prop from a
parent that no longer holds it. Backed by the in-memory
app/tickets/store.py - see its docstring for scope/limitations.

Mounted at /api/tickets in app/main.py.
"""

from fastapi import APIRouter

from app.tickets import store
from app.tickets.schemas import ReviewedTicket

router = APIRouter()


@router.post("/reviewed", response_model=ReviewedTicket)
def record_reviewed_ticket(ticket: ReviewedTicket) -> ReviewedTicket:
    store.upsert_reviewed_ticket(ticket)
    return ticket


@router.get("/reviewed", response_model=list[ReviewedTicket])
def get_reviewed_tickets() -> list[ReviewedTicket]:
    return store.list_reviewed_tickets()
