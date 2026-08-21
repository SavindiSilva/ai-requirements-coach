"""In-memory Jira connection state shape.

Mirrors app/coaching/state.py's CoachingSessionState convention: a plain
TypedDict, not a Pydantic model, since this is internal process state, not
a request/response boundary.
"""

from typing import TypedDict


class JiraConnectionState(TypedDict):
    access_token: str
    refresh_token: str
    expires_at: float  # epoch seconds
    cloud_id: str
    scope: str
