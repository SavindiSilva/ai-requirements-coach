"""SQLite-backed reviewed-ticket history store.

Mirrors app/jira/store.py's shape conceptually (no auth/user system yet to
scope by - app/auth/ is an empty stub), but persists to a local SQLite file
(`DB_PATH`, sourced from `settings.tickets_db_path`, default `data/tickets.db`,
gitignored) instead of a process-local list, so reviewed-ticket history
survives a backend restart. Not safe across multiple worker processes writing
concurrently - same class of limitation as app/jira/store.py's single
in-memory connection.

A ticket is upserted by issue_key: recorded once right after analysis and
again if the user goes on to finish coaching, so the second call updates
the existing row (moving it to the front) rather than inserting a duplicate
row for the same ticket. Tickets with no issue_key (entered manually, no
source_issue_key) are never deduplicated - each is inserted as a new row.
"""

import sqlite3
from pathlib import Path

from app.core.config import settings
from app.tickets.schemas import ReviewedTicket

DB_PATH = Path(settings.tickets_db_path)


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    """Create the reviewed_tickets table if it doesn't already exist.

    Safe to call on every app startup.
    """
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reviewed_tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    issue_key TEXT,
                    title TEXT NOT NULL,
                    readiness REAL NOT NULL,
                    reviewed_at REAL NOT NULL,
                    stop_reason TEXT
                )
                """
            )
    finally:
        conn.close()


def upsert_reviewed_ticket(ticket: ReviewedTicket) -> None:
    conn = _connect()
    try:
        with conn:
            if ticket.issue_key:
                conn.execute("DELETE FROM reviewed_tickets WHERE issue_key = ?", (ticket.issue_key,))
            conn.execute(
                "INSERT INTO reviewed_tickets (issue_key, title, readiness, reviewed_at, stop_reason) "
                "VALUES (?, ?, ?, ?, ?)",
                (ticket.issue_key, ticket.title, ticket.readiness, ticket.reviewed_at, ticket.stop_reason),
            )
    finally:
        conn.close()


def list_reviewed_tickets() -> list[ReviewedTicket]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT issue_key, title, readiness, reviewed_at, stop_reason "
            "FROM reviewed_tickets ORDER BY id DESC"
        ).fetchall()
    finally:
        conn.close()
    return [
        ReviewedTicket(issue_key=row[0], title=row[1], readiness=row[2], reviewed_at=row[3], stop_reason=row[4])
        for row in rows
    ]
