"""In-memory Jira OAuth connection store.

TEMPORARY SCAFFOLDING - NOT SUITABLE FOR PRODUCTION.

Mirrors app/coaching/store.py's shape (a process-local dict, narrow
exception types per invalid transition, validate-before-mutate), but for a
single Jira connection instead of many coaching sessions, because there is
no auth/user system yet (app/auth/ is an empty stub) to scope connections
by. This does not survive a process restart, is not safe across multiple
worker processes, and supports exactly one Jira connection process-wide.

Must be replaced by real persistence (CLAUDE.md section 21, `jira_connections`)
and multi-user auth before production use - see docs/architecture.md.
"""

import time
import uuid

from app.jira.state import JiraConnectionState

_CONNECTION: JiraConnectionState | None = None
_PENDING_STATES: dict[str, float] = {}

_OAUTH_STATE_TTL_SECONDS = 600


class JiraNotConnectedError(Exception):
    """Raised when a Jira-authenticated call is made with no stored connection."""


class InvalidOAuthStateError(Exception):
    """Raised when an OAuth callback's state parameter is missing, unknown, or expired."""


def create_pending_state() -> str:
    """Generate and remember a CSRF state value for one authorize->callback round trip."""
    state = str(uuid.uuid4())
    _PENDING_STATES[state] = time.time()
    return state


def validate_and_consume_state(state: str | None) -> None:
    """Validate an OAuth callback's state parameter, then consume it (single use).

    Raises without mutating anything further if the state is missing,
    unknown, or expired.
    """
    if not state or state not in _PENDING_STATES:
        raise InvalidOAuthStateError("Unknown or missing OAuth state parameter.")

    created_at = _PENDING_STATES.pop(state)
    if time.time() - created_at > _OAUTH_STATE_TTL_SECONDS:
        raise InvalidOAuthStateError("OAuth state parameter has expired.")


def save_connection(connection: JiraConnectionState) -> None:
    global _CONNECTION
    _CONNECTION = connection


def get_connection() -> JiraConnectionState:
    if _CONNECTION is None:
        raise JiraNotConnectedError("No Jira connection is currently stored. Connect Jira first.")
    return _CONNECTION


def is_connected() -> bool:
    return _CONNECTION is not None
