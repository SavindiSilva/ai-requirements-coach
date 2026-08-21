"""Atlassian OAuth 2.0 (3LO) token exchange for Jira.

Handles only the pure HTTP calls to Atlassian's own OAuth endpoints
(authorize-URL construction, code-for-token exchange, refresh,
accessible-resources lookup). Connection storage lives in app/jira/store.py;
deciding *when* to refresh lives in app/jira/client.py (the one place that
actually makes authenticated Jira REST calls).

Uses bare module-level httpx.get/post calls rather than a persistent
httpx.Client singleton (unlike app/agent/llm.py::get_client() or
app/rag/embeddings.py::get_embedding_client()) - those hold a *static* API
key for the process lifetime, whereas here the credential (the Jira access
token) changes over time via refresh, so there is nothing worth caching in
a long-lived client.
"""

import time

import httpx

from app.core.config import settings
from app.jira.state import JiraConnectionState

AUTHORIZE_URL = "https://auth.atlassian.com/authorize"
TOKEN_URL = "https://auth.atlassian.com/oauth/token"
ACCESSIBLE_RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"


class JiraOAuthError(Exception):
    """Raised when an Atlassian OAuth call fails or returns an unexpected response."""


def build_authorize_url(state: str) -> str:
    url = httpx.URL(
        AUTHORIZE_URL,
        params={
            "audience": "api.atlassian.com",
            "client_id": settings.jira_client_id,
            "scope": settings.jira_scopes,
            "redirect_uri": settings.jira_redirect_uri,
            "state": state,
            "response_type": "code",
            "prompt": "consent",
        },
    )
    return str(url)


def _fetch_cloud_id(access_token: str) -> str:
    try:
        response = httpx.get(
            ACCESSIBLE_RESOURCES_URL,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise JiraOAuthError(f"Failed to retrieve accessible Jira resources: {exc}") from exc

    resources = response.json()
    if not resources:
        raise JiraOAuthError("This Jira account has no accessible sites to connect.")

    return resources[0]["id"]


def exchange_code_for_tokens(code: str) -> JiraConnectionState:
    """Exchange an OAuth authorization code for an access/refresh token pair.

    Also resolves the Jira Cloud id via the accessible-resources endpoint,
    since every subsequent Jira REST call needs it (CLAUDE.md section 14).
    """
    try:
        response = httpx.post(
            TOKEN_URL,
            json={
                "grant_type": "authorization_code",
                "client_id": settings.jira_client_id,
                "client_secret": settings.jira_client_secret,
                "code": code,
                "redirect_uri": settings.jira_redirect_uri,
            },
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise JiraOAuthError(f"Failed to exchange authorization code for tokens: {exc}") from exc

    data = response.json()
    cloud_id = _fetch_cloud_id(data["access_token"])

    return JiraConnectionState(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_at=time.time() + data["expires_in"],
        cloud_id=cloud_id,
        scope=data.get("scope", ""),
    )


def refresh_access_token(connection: JiraConnectionState) -> JiraConnectionState:
    """Exchange a refresh token for a new access token, keeping the existing cloud_id.

    Deliberately does not re-call the accessible-resources endpoint - the
    cloud_id does not change between refreshes, and refetching it on every
    refresh would be an unnecessary extra network call and failure point.
    """
    try:
        response = httpx.post(
            TOKEN_URL,
            json={
                "grant_type": "refresh_token",
                "client_id": settings.jira_client_id,
                "client_secret": settings.jira_client_secret,
                "refresh_token": connection["refresh_token"],
            },
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise JiraOAuthError(f"Failed to refresh Jira access token: {exc}") from exc

    data = response.json()
    return JiraConnectionState(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token", connection["refresh_token"]),
        expires_at=time.time() + data["expires_in"],
        cloud_id=connection["cloud_id"],
        scope=data.get("scope", connection["scope"]),
    )
