"""Authenticated Jira Cloud REST API v3 calls.

Each function makes a fresh HTTP request per call rather than holding a
persistent httpx.Client (see app/jira/oauth.py's module docstring for why:
the bearer token can change between calls via refresh).

Uses GET /rest/api/3/search/jql for issue listing - the classic GET/POST
/rest/api/3/search endpoints were removed by Atlassian (returning 410 Gone)
as of the enhanced-JQL-search migration; see
https://developer.atlassian.com/changelog/#CHANGE-2046 and
docs/architecture.md §12 for details. /search/jql defaults `fields` to
`id` only (unlike the old /search's broader default), so `list_issues()`
must keep passing `fields` explicitly - it already did before this change,
so no behavioral difference there. Pagination on /search/jql is
`nextPageToken`-based rather than `startAt`-based, but `list_issues()`
only ever fetched a single page (`maxResults=50`, no pagination loop)
before and after this change, so that shift doesn't affect this function.
"""

import time

import httpx

from app.analysis.schemas import RelatedIssue
from app.coaching.schemas import FinalRequirementContent
from app.jira import oauth, store
from app.jira.parsing import adf_to_plain_text, extract_related_issues, format_final_requirement_text, plain_text_to_adf
from app.jira.schemas import JiraIssueDetail, JiraIssueSummary, JiraProject
from app.jira.state import JiraConnectionState


class JiraAPIError(Exception):
    """Raised when a Jira Cloud REST API call fails or returns an unexpected response."""


def _base_url(cloud_id: str) -> str:
    return f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3"


def get_valid_connection() -> JiraConnectionState:
    """Return the stored connection, transparently refreshing an expired access token.

    Raises store.JiraNotConnectedError (unchanged) if there is no connection
    at all - that is a distinct condition from "connected but expired".
    """
    connection = store.get_connection()

    if time.time() >= connection["expires_at"]:
        connection = oauth.refresh_access_token(connection)
        store.save_connection(connection)

    return connection


def _get(path: str, params: dict | None = None) -> dict:
    connection = get_valid_connection()
    url = f"{_base_url(connection['cloud_id'])}{path}"

    try:
        response = httpx.get(
            url,
            headers={
                "Authorization": f"Bearer {connection['access_token']}",
                "Accept": "application/json",
            },
            params=params or {},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise JiraAPIError(f"Jira API request to {path} failed: {exc}") from exc

    return response.json()


def _put(path: str, json_body: dict) -> None:
    connection = get_valid_connection()
    url = f"{_base_url(connection['cloud_id'])}{path}"

    try:
        response = httpx.put(
            url,
            headers={
                "Authorization": f"Bearer {connection['access_token']}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json=json_body,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise JiraAPIError(f"Jira API request to {path} failed: {exc}") from exc


def list_projects() -> list[JiraProject]:
    data = _get("/project/search", params={"maxResults": 50})
    return [JiraProject(id=p["id"], key=p["key"], name=p["name"]) for p in data.get("values", [])]


def list_issues(project_id: str) -> list[JiraIssueSummary]:
    data = _get(
        "/search/jql",
        params={
            "jql": f'project = "{project_id}" ORDER BY created DESC',
            "fields": "summary,status,issuetype",
            "maxResults": 50,
        },
    )
    return [
        JiraIssueSummary(
            key=issue["key"],
            summary=issue["fields"]["summary"],
            status=issue["fields"]["status"]["name"],
            issue_type=issue["fields"]["issuetype"]["name"],
        )
        for issue in data.get("issues", [])
    ]


def get_issue(issue_key: str) -> JiraIssueDetail:
    data = _get(
        f"/issue/{issue_key}",
        params={"fields": "summary,description,status,issuetype,issuelinks,subtasks,parent"},
    )
    fields = data["fields"]

    return JiraIssueDetail(
        key=data["key"],
        summary=fields["summary"],
        description=adf_to_plain_text(fields.get("description")),
        status=fields["status"]["name"],
        issue_type=fields["issuetype"]["name"],
        links=extract_related_issues(fields),
    )


def get_issue_links(issue_key: str) -> list[RelatedIssue]:
    return get_issue(issue_key).links


def update_issue(issue_key: str, final_requirement: FinalRequirementContent) -> None:
    """Overwrite an issue's description with the finalized development-ready requirement.

    MVP scope: description only - never touches custom fields, assignee,
    priority, status, story points, or any other field. Callers are
    responsible for only invoking this after explicit user approval
    (CLAUDE.md section 17); this function itself performs the write
    unconditionally once called.
    """
    description_adf = plain_text_to_adf(format_final_requirement_text(final_requirement))
    _put(f"/issue/{issue_key}", {"fields": {"description": description_adf}})
