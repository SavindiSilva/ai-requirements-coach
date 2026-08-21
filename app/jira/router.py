"""FastAPI routes for Jira OAuth (Atlassian 3LO) and Jira read APIs.

Two routers, included separately in app/main.py because their paths follow
different conventions:
- `oauth_router`: /jira/authorize, /jira/callback - the callback path must
  exactly match settings.jira_redirect_uri as registered in the Atlassian
  Developer Console, so it cannot live under the /api prefix every other
  route in this app uses.
- `router`: /api/jira/* - Jira application-data reads, following the same
  /api prefix convention as app/analysis/router.py and app/coaching/router.py.

Do not implement issue-update/write endpoints here - out of scope for this
slice (CLAUDE.md section 17: never auto-update Jira without explicit user
approval, which does not exist yet).
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.analysis.schemas import RelatedIssue
from app.core.config import settings
from app.jira import client, oauth, store
from app.jira.client import JiraAPIError
from app.jira.oauth import JiraOAuthError
from app.jira.schemas import JiraIssueDetail, JiraIssueSummary, JiraProject, JiraStatusResponse
from app.jira.store import InvalidOAuthStateError, JiraNotConnectedError

oauth_router = APIRouter()
router = APIRouter()


@oauth_router.get("/authorize")
def jira_authorize() -> RedirectResponse:
    state = store.create_pending_state()
    return RedirectResponse(oauth.build_authorize_url(state))


@oauth_router.get("/callback")
def jira_callback(
    code: str | None = None, state: str | None = None, error: str | None = None
) -> RedirectResponse:
    if error:
        raise HTTPException(status_code=400, detail=f"Jira authorization was denied: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code from Jira callback.")

    try:
        store.validate_and_consume_state(state)
    except InvalidOAuthStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        connection = oauth.exchange_code_for_tokens(code)
    except JiraOAuthError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    store.save_connection(connection)
    return RedirectResponse(settings.frontend_url)


@router.get("/status", response_model=JiraStatusResponse)
def jira_status() -> JiraStatusResponse:
    return JiraStatusResponse(connected=store.is_connected())


@router.get("/projects", response_model=list[JiraProject])
def jira_projects() -> list[JiraProject]:
    try:
        return client.list_projects()
    except JiraNotConnectedError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except JiraAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/projects/{project_id}/issues", response_model=list[JiraIssueSummary])
def jira_project_issues(project_id: str) -> list[JiraIssueSummary]:
    try:
        return client.list_issues(project_id)
    except JiraNotConnectedError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except JiraAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/issues/{issue_key}", response_model=JiraIssueDetail)
def jira_issue(issue_key: str) -> JiraIssueDetail:
    try:
        return client.get_issue(issue_key)
    except JiraNotConnectedError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except JiraAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/issues/{issue_key}/links", response_model=list[RelatedIssue])
def jira_issue_links(issue_key: str) -> list[RelatedIssue]:
    try:
        return client.get_issue_links(issue_key)
    except JiraNotConnectedError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except JiraAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
