"""Tests for the Jira integration module (app/jira/).

Follows the existing test conventions (docs/skills.md section 6):
- Pure/deterministic logic (app/jira/parsing.py) is tested directly against
  hand-built fixture dicts, no network calls - mirrors how
  select_weakest_criterion/should_stop_coaching are tested.
- Real external calls (Atlassian OAuth, Jira REST API) cannot follow the
  project's "hit the real API, no mocking" convention the way Claude/OpenAI
  calls do, because completing a real OAuth consent flow requires a live
  user in a browser and cannot run headlessly in CI. httpx calls are
  monkeypatched at the module level instead, consistent with how the rest
  of this codebase monkeypatches module-level functions directly (e.g.
  app.coaching.router.generate_clarification_question in test_coaching.py)
  rather than introducing a new mocking library/dependency.
"""

import json as json_module
import time

import httpx
import pytest

from app.agent.prompts import build_user_prompt
from app.analysis.schemas import RelatedIssue, TicketInput
from app.coaching.schemas import FinalRequirementContent
from app.jira import client, oauth, store
from app.jira.client import JiraAPIError
from app.jira.oauth import JiraOAuthError
from app.jira.parsing import (
    adf_to_plain_text,
    extract_related_issues,
    format_final_requirement_text,
    plain_text_to_adf,
)
from app.jira.schemas import JiraProject
from app.jira.state import JiraConnectionState
from app.jira.store import InvalidOAuthStateError, JiraNotConnectedError
from app.main import app
from fastapi.testclient import TestClient

client_app = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_jira_store():
    """Every test gets a clean in-memory store - this module-level state
    would otherwise leak between tests, same risk app/coaching/store.py's
    _SESSIONS dict has (mitigated there by using fresh session ids)."""
    store._CONNECTION = None
    store._PENDING_STATES.clear()
    yield
    store._CONNECTION = None
    store._PENDING_STATES.clear()


def _make_connection(expires_in_seconds: float = 3600) -> JiraConnectionState:
    return JiraConnectionState(
        access_token="access-token-123",
        refresh_token="refresh-token-123",
        expires_at=time.time() + expires_in_seconds,
        cloud_id="cloud-id-123",
        scope="read:jira-work offline_access",
    )


# --- app/jira/parsing.py: adf_to_plain_text ---------------------------------


def test_adf_to_plain_text_none_returns_empty_string():
    assert adf_to_plain_text(None) == ""


def test_adf_to_plain_text_empty_dict_returns_empty_string():
    assert adf_to_plain_text({}) == ""


def test_adf_to_plain_text_single_paragraph():
    node = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "Users should receive notifications."}],
            }
        ],
    }
    assert adf_to_plain_text(node) == "Users should receive notifications."


def test_adf_to_plain_text_multiple_paragraphs_are_separated():
    node = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "First paragraph."}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "Second paragraph."}]},
        ],
    }
    result = adf_to_plain_text(node)
    assert "First paragraph." in result
    assert "Second paragraph." in result
    assert result.index("First paragraph.") < result.index("Second paragraph.")


def test_adf_to_plain_text_ignores_unknown_node_types_but_walks_into_content():
    node = {
        "type": "doc",
        "content": [
            {
                "type": "table",  # unhandled block type
                "content": [
                    {
                        "type": "tableRow",
                        "content": [{"type": "text", "text": "cell text"}],
                    }
                ],
            }
        ],
    }
    assert "cell text" in adf_to_plain_text(node)


# --- app/jira/parsing.py: extract_related_issues ----------------------------


def test_extract_related_issues_empty_fields_returns_empty_list():
    assert extract_related_issues({}) == []


def test_extract_related_issues_outward_link():
    fields = {
        "issuelinks": [
            {
                "type": {"outward": "blocks", "inward": "is blocked by"},
                "outwardIssue": {"key": "PROJ-101", "fields": {"summary": "Create Notification API"}},
            }
        ]
    }
    result = extract_related_issues(fields)
    assert result == [RelatedIssue(key="PROJ-101", relationship="blocks", summary="Create Notification API")]


def test_extract_related_issues_inward_link():
    fields = {
        "issuelinks": [
            {
                "type": {"outward": "blocks", "inward": "is blocked by"},
                "inwardIssue": {"key": "PROJ-102", "fields": {"summary": "Create Notification Settings"}},
            }
        ]
    }
    result = extract_related_issues(fields)
    assert result == [
        RelatedIssue(key="PROJ-102", relationship="is blocked by", summary="Create Notification Settings")
    ]


def test_extract_related_issues_parent():
    fields = {"parent": {"key": "PROJ-1", "fields": {"summary": "Notification Epic"}}}
    result = extract_related_issues(fields)
    assert result == [RelatedIssue(key="PROJ-1", relationship="parent", summary="Notification Epic")]


def test_extract_related_issues_subtasks():
    fields = {
        "subtasks": [
            {"key": "PROJ-10", "fields": {"summary": "Subtask A"}},
            {"key": "PROJ-11", "fields": {"summary": "Subtask B"}},
        ]
    }
    result = extract_related_issues(fields)
    assert result == [
        RelatedIssue(key="PROJ-10", relationship="subtask", summary="Subtask A"),
        RelatedIssue(key="PROJ-11", relationship="subtask", summary="Subtask B"),
    ]


def test_extract_related_issues_combines_links_parent_and_subtasks():
    fields = {
        "issuelinks": [
            {"type": {"outward": "relates to"}, "outwardIssue": {"key": "PROJ-5", "fields": {}}},
        ],
        "parent": {"key": "PROJ-1", "fields": {"summary": "Epic"}},
        "subtasks": [{"key": "PROJ-10", "fields": {"summary": "Subtask A"}}],
    }
    result = extract_related_issues(fields)
    assert [r.key for r in result] == ["PROJ-5", "PROJ-1", "PROJ-10"]
    assert result[0].summary is None  # missing summary field handled gracefully


# --- app/jira/store.py -------------------------------------------------------


def test_store_create_and_validate_pending_state_succeeds():
    state = store.create_pending_state()
    store.validate_and_consume_state(state)  # must not raise


def test_store_validate_state_missing_raises():
    with pytest.raises(InvalidOAuthStateError):
        store.validate_and_consume_state(None)


def test_store_validate_state_unknown_raises():
    with pytest.raises(InvalidOAuthStateError):
        store.validate_and_consume_state("never-issued-state")


def test_store_validate_state_is_single_use():
    state = store.create_pending_state()
    store.validate_and_consume_state(state)
    with pytest.raises(InvalidOAuthStateError):
        store.validate_and_consume_state(state)


def test_store_validate_state_expired_raises(monkeypatch):
    state = store.create_pending_state()
    future = time.time() + 601
    monkeypatch.setattr(store.time, "time", lambda: future)
    with pytest.raises(InvalidOAuthStateError):
        store.validate_and_consume_state(state)


def test_store_get_connection_raises_when_not_connected():
    assert store.is_connected() is False
    with pytest.raises(JiraNotConnectedError):
        store.get_connection()


def test_store_save_and_get_connection_roundtrip():
    connection = _make_connection()
    store.save_connection(connection)
    assert store.is_connected() is True
    assert store.get_connection() == connection


# --- app/jira/oauth.py --------------------------------------------------------


def test_build_authorize_url_contains_required_params(monkeypatch):
    monkeypatch.setattr(oauth.settings, "jira_client_id", "test-client-id")
    monkeypatch.setattr(oauth.settings, "jira_scopes", "read:jira-work offline_access")
    monkeypatch.setattr(oauth.settings, "jira_redirect_uri", "http://localhost:8000/jira/callback")

    url = oauth.build_authorize_url("some-state-value")

    assert url.startswith("https://auth.atlassian.com/authorize")
    assert "client_id=test-client-id" in url
    assert "state=some-state-value" in url
    assert "response_type=code" in url
    assert "audience=api.atlassian.com" in url


def test_exchange_code_for_tokens_success(monkeypatch):
    def _fake_post(url, json=None, **kwargs):
        assert url == oauth.TOKEN_URL
        assert json["grant_type"] == "authorization_code"
        assert json["code"] == "auth-code-123"
        return httpx.Response(
            200,
            json={
                "access_token": "new-access-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
                "scope": "read:jira-work offline_access",
            },
            request=httpx.Request("POST", url),
        )

    def _fake_get(url, headers=None, **kwargs):
        assert url == oauth.ACCESSIBLE_RESOURCES_URL
        assert headers["Authorization"] == "Bearer new-access-token"
        return httpx.Response(
            200,
            json=[{"id": "cloud-id-456", "name": "Test Site"}],
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(oauth.httpx, "post", _fake_post)
    monkeypatch.setattr(oauth.httpx, "get", _fake_get)

    connection = oauth.exchange_code_for_tokens("auth-code-123")

    assert connection["access_token"] == "new-access-token"
    assert connection["refresh_token"] == "new-refresh-token"
    assert connection["cloud_id"] == "cloud-id-456"


def test_exchange_code_for_tokens_http_failure_raises_jira_oauth_error(monkeypatch):
    def _fake_post(url, json=None, **kwargs):
        return httpx.Response(400, json={"error": "invalid_grant"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(oauth.httpx, "post", _fake_post)

    with pytest.raises(JiraOAuthError):
        oauth.exchange_code_for_tokens("bad-code")


def test_exchange_code_for_tokens_no_accessible_resources_raises(monkeypatch):
    def _fake_post(url, json=None, **kwargs):
        return httpx.Response(
            200,
            json={"access_token": "tok", "refresh_token": "ref", "expires_in": 3600, "scope": ""},
            request=httpx.Request("POST", url),
        )

    def _fake_get(url, headers=None, **kwargs):
        return httpx.Response(200, json=[], request=httpx.Request("GET", url))

    monkeypatch.setattr(oauth.httpx, "post", _fake_post)
    monkeypatch.setattr(oauth.httpx, "get", _fake_get)

    with pytest.raises(JiraOAuthError):
        oauth.exchange_code_for_tokens("auth-code-123")


def test_refresh_access_token_success_preserves_cloud_id(monkeypatch):
    connection = _make_connection()

    def _fake_post(url, json=None, **kwargs):
        assert json["grant_type"] == "refresh_token"
        assert json["refresh_token"] == connection["refresh_token"]
        return httpx.Response(
            200,
            json={"access_token": "refreshed-access-token", "expires_in": 3600},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(oauth.httpx, "post", _fake_post)

    refreshed = oauth.refresh_access_token(connection)

    assert refreshed["access_token"] == "refreshed-access-token"
    assert refreshed["cloud_id"] == connection["cloud_id"]
    # refresh_token omitted from response -> falls back to the existing one
    assert refreshed["refresh_token"] == connection["refresh_token"]


def test_refresh_access_token_http_failure_raises(monkeypatch):
    connection = _make_connection()

    def _fake_post(url, json=None, **kwargs):
        return httpx.Response(401, json={"error": "invalid_grant"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(oauth.httpx, "post", _fake_post)

    with pytest.raises(JiraOAuthError):
        oauth.refresh_access_token(connection)


# --- app/jira/client.py -------------------------------------------------------


def test_get_valid_connection_raises_when_not_connected():
    with pytest.raises(JiraNotConnectedError):
        client.get_valid_connection()


def test_get_valid_connection_returns_unexpired_connection_without_refresh(monkeypatch):
    connection = _make_connection(expires_in_seconds=3600)
    store.save_connection(connection)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("refresh_access_token must not be called for an unexpired token")

    monkeypatch.setattr(client.oauth, "refresh_access_token", _fail_if_called)

    result = client.get_valid_connection()
    assert result == connection


def test_get_valid_connection_refreshes_expired_connection(monkeypatch):
    expired = _make_connection(expires_in_seconds=-10)
    store.save_connection(expired)

    refreshed = _make_connection(expires_in_seconds=3600)

    monkeypatch.setattr(client.oauth, "refresh_access_token", lambda conn: refreshed)

    result = client.get_valid_connection()

    assert result == refreshed
    assert store.get_connection() == refreshed  # persisted back to the store


def test_list_projects_parses_response(monkeypatch):
    store.save_connection(_make_connection())

    def _fake_get(url, headers=None, params=None, **kwargs):
        assert "/project/search" in url
        return httpx.Response(
            200,
            json={"values": [{"id": "10001", "key": "PROJ", "name": "Sample Project"}]},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(client.httpx, "get", _fake_get)

    projects = client.list_projects()
    assert len(projects) == 1
    assert projects[0].key == "PROJ"
    assert projects[0].name == "Sample Project"


def test_list_projects_not_connected_raises_without_http_call(monkeypatch):
    def _fail_if_called(*args, **kwargs):
        raise AssertionError("httpx.get must not be called when Jira is not connected")

    monkeypatch.setattr(client.httpx, "get", _fail_if_called)

    with pytest.raises(JiraNotConnectedError):
        client.list_projects()


def test_list_projects_http_failure_raises_jira_api_error(monkeypatch):
    store.save_connection(_make_connection())

    def _fake_get(url, headers=None, params=None, **kwargs):
        return httpx.Response(500, json={"error": "boom"}, request=httpx.Request("GET", url))

    monkeypatch.setattr(client.httpx, "get", _fake_get)

    with pytest.raises(JiraAPIError):
        client.list_projects()


def test_list_issues_uses_search_jql_endpoint_not_deprecated_search(monkeypatch):
    # Regression test: GET/POST /rest/api/3/search were removed by Atlassian
    # (410 Gone) - list_issues() must call the replacement /search/jql
    # endpoint instead. See CHANGE-2046.
    store.save_connection(_make_connection())

    def _fake_get(url, headers=None, params=None, **kwargs):
        assert url.endswith("/search/jql")
        assert 'project = "PROJ"' in params["jql"]
        return httpx.Response(
            200,
            json={"isLast": True, "nextPageToken": None, "issues": []},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(client.httpx, "get", _fake_get)

    assert client.list_issues("PROJ") == []


def test_list_issues_parses_response(monkeypatch):
    store.save_connection(_make_connection())

    def _fake_get(url, headers=None, params=None, **kwargs):
        assert url.endswith("/search/jql")
        assert 'project = "PROJ"' in params["jql"]
        assert params["fields"] == "summary,status,issuetype"
        # Real /search/jql response shape (isLast/nextPageToken, no
        # startAt/total) - list_issues() must not depend on those old
        # top-level fields, only on "issues".
        return httpx.Response(
            200,
            json={
                "isLast": True,
                "issues": [
                    {
                        "key": "PROJ-1",
                        "fields": {
                            "summary": "Add notification feature",
                            "status": {"name": "To Do"},
                            "issuetype": {"name": "Story"},
                        },
                    }
                ],
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(client.httpx, "get", _fake_get)

    issues = client.list_issues("PROJ")
    assert len(issues) == 1
    assert issues[0].key == "PROJ-1"
    assert issues[0].status == "To Do"
    assert issues[0].issue_type == "Story"


def test_get_issue_parses_description_and_links(monkeypatch):
    store.save_connection(_make_connection())

    def _fake_get(url, headers=None, params=None, **kwargs):
        assert "/issue/PROJ-1" in url
        return httpx.Response(
            200,
            json={
                "key": "PROJ-1",
                "fields": {
                    "summary": "Add notification feature",
                    "description": {
                        "type": "doc",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "Notify users."}]}
                        ],
                    },
                    "status": {"name": "In Progress"},
                    "issuetype": {"name": "Story"},
                    "issuelinks": [
                        {
                            "type": {"outward": "blocks"},
                            "outwardIssue": {"key": "PROJ-2", "fields": {"summary": "Dependency"}},
                        }
                    ],
                    "subtasks": [],
                },
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(client.httpx, "get", _fake_get)

    issue = client.get_issue("PROJ-1")

    assert issue.key == "PROJ-1"
    assert issue.summary == "Add notification feature"
    assert issue.description == "Notify users."
    assert issue.status == "In Progress"
    assert issue.links == [RelatedIssue(key="PROJ-2", relationship="blocks", summary="Dependency")]


def test_get_issue_links_returns_issue_links(monkeypatch):
    store.save_connection(_make_connection())

    def _fake_get(url, headers=None, params=None, **kwargs):
        return httpx.Response(
            200,
            json={
                "key": "PROJ-1",
                "fields": {
                    "summary": "S",
                    "description": None,
                    "status": {"name": "To Do"},
                    "issuetype": {"name": "Story"},
                    "issuelinks": [],
                    "parent": {"key": "PROJ-0", "fields": {"summary": "Epic"}},
                },
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(client.httpx, "get", _fake_get)

    links = client.get_issue_links("PROJ-1")
    assert links == [RelatedIssue(key="PROJ-0", relationship="parent", summary="Epic")]


# --- app/jira/router.py: /jira/authorize, /jira/callback --------------------


def test_jira_authorize_redirects_to_atlassian(monkeypatch):
    monkeypatch.setattr(oauth.settings, "jira_client_id", "test-client-id")

    response = client_app.get("/jira/authorize", follow_redirects=False)

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert location.startswith("https://auth.atlassian.com/authorize")
    assert "client_id=test-client-id" in location
    assert "state=" in location


def test_jira_callback_missing_code_returns_400():
    response = client_app.get("/jira/callback", params={"state": "whatever"})
    assert response.status_code == 400


def test_jira_callback_error_param_returns_400():
    response = client_app.get("/jira/callback", params={"error": "access_denied"})
    assert response.status_code == 400


def test_jira_callback_invalid_state_returns_400_without_exchanging_code(monkeypatch):
    def _fail_if_called(*args, **kwargs):
        raise AssertionError("exchange_code_for_tokens must not be called when state is invalid")

    monkeypatch.setattr("app.jira.router.oauth.exchange_code_for_tokens", _fail_if_called)

    response = client_app.get("/jira/callback", params={"code": "abc", "state": "not-a-real-state"})
    assert response.status_code == 400
    assert store.is_connected() is False


def test_jira_callback_success_stores_connection_and_redirects(monkeypatch):
    state = store.create_pending_state()
    connection = _make_connection()

    monkeypatch.setattr("app.jira.router.oauth.exchange_code_for_tokens", lambda code: connection)

    response = client_app.get(
        "/jira/callback", params={"code": "abc", "state": state}, follow_redirects=False
    )

    assert response.status_code in (302, 307)
    assert store.is_connected() is True
    assert store.get_connection() == connection


def test_jira_callback_oauth_failure_returns_502(monkeypatch):
    state = store.create_pending_state()

    def _raise(code):
        raise JiraOAuthError("token exchange failed")

    monkeypatch.setattr("app.jira.router.oauth.exchange_code_for_tokens", _raise)

    response = client_app.get("/jira/callback", params={"code": "abc", "state": state})
    assert response.status_code == 502
    assert store.is_connected() is False


# --- app/jira/router.py: /api/jira/* -----------------------------------------


def test_jira_status_not_connected():
    response = client_app.get("/api/jira/status")
    assert response.status_code == 200
    assert response.json() == {"connected": False}


def test_jira_status_connected():
    store.save_connection(_make_connection())
    response = client_app.get("/api/jira/status")
    assert response.status_code == 200
    assert response.json() == {"connected": True}


def test_jira_projects_not_connected_returns_401():
    response = client_app.get("/api/jira/projects")
    assert response.status_code == 401


def test_jira_projects_returns_data(monkeypatch):
    store.save_connection(_make_connection())
    monkeypatch.setattr(
        "app.jira.router.client.list_projects",
        lambda: [JiraProject(id="1", key="PROJ", name="Sample")],
    )

    response = client_app.get("/api/jira/projects")
    assert response.status_code == 200
    assert response.json() == [{"id": "1", "key": "PROJ", "name": "Sample"}]


def test_jira_projects_api_failure_returns_502(monkeypatch):
    store.save_connection(_make_connection())

    def _raise():
        raise JiraAPIError("upstream failure")

    monkeypatch.setattr("app.jira.router.client.list_projects", _raise)

    response = client_app.get("/api/jira/projects")
    assert response.status_code == 502


def test_jira_project_issues_not_connected_returns_401():
    response = client_app.get("/api/jira/projects/PROJ/issues")
    assert response.status_code == 401


def test_jira_issue_not_connected_returns_401():
    response = client_app.get("/api/jira/issues/PROJ-1")
    assert response.status_code == 401


def test_jira_issue_links_not_connected_returns_401():
    response = client_app.get("/api/jira/issues/PROJ-1/links")
    assert response.status_code == 401


# --- app/jira/parsing.py: format_final_requirement_text -----------------------


def _make_final_requirement(
    user_story: str = "As a user, I want X so that Y.",
    acceptance_criteria: list[str] | None = None,
    scope: list[str] | None = None,
    assumptions: list[str] | None = None,
    dependencies: list[str] | None = None,
) -> FinalRequirementContent:
    return FinalRequirementContent(
        user_story=user_story,
        acceptance_criteria=acceptance_criteria if acceptance_criteria is not None else ["Given A, when B, then C."],
        scope=scope if scope is not None else ["In scope: X."],
        assumptions=assumptions if assumptions is not None else ["Assumes Y exists."],
        dependencies=dependencies if dependencies is not None else ["Depends on Z."],
    )


def test_format_final_requirement_text_includes_all_sections():
    text = format_final_requirement_text(_make_final_requirement())

    assert "User Story:" in text
    assert "As a user, I want X so that Y." in text
    assert "Acceptance Criteria:" in text
    assert "- Given A, when B, then C." in text
    assert "Scope:" in text
    assert "- In scope: X." in text
    assert "Assumptions:" in text
    assert "- Assumes Y exists." in text
    assert "Dependencies:" in text
    assert "- Depends on Z." in text


def test_format_final_requirement_text_empty_section_shows_none():
    text = format_final_requirement_text(_make_final_requirement(dependencies=[]))
    assert "Dependencies:\n\n(none)" in text


def test_format_final_requirement_text_title_and_body_are_separate_blocks():
    # plain_text_to_adf() relies on a blank line between a section's title
    # and its body to render them as distinct ADF nodes.
    text = format_final_requirement_text(_make_final_requirement())
    assert "Acceptance Criteria:\n\n- Given A, when B, then C." in text


# --- app/jira/parsing.py: plain_text_to_adf ------------------------------------


def test_plain_text_to_adf_empty_string_returns_valid_empty_doc():
    doc = plain_text_to_adf("")
    assert doc["type"] == "doc"
    assert doc["version"] == 1
    assert doc["content"] == [{"type": "paragraph", "content": []}]


def test_plain_text_to_adf_single_paragraph():
    doc = plain_text_to_adf("Hello world.")
    assert doc["content"] == [{"type": "paragraph", "content": [{"type": "text", "text": "Hello world."}]}]


def test_plain_text_to_adf_bullet_block_becomes_bullet_list():
    doc = plain_text_to_adf("- Item one\n- Item two")
    assert doc["content"] == [
        {
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Item one"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Item two"}]}]},
            ],
        }
    ]


def test_plain_text_to_adf_title_then_bullets_are_separate_nodes():
    doc = plain_text_to_adf("Acceptance Criteria:\n\n- Item one\n- Item two")
    assert len(doc["content"]) == 2
    assert doc["content"][0] == {"type": "paragraph", "content": [{"type": "text", "text": "Acceptance Criteria:"}]}
    assert doc["content"][1]["type"] == "bulletList"


def test_plain_text_to_adf_roundtrips_format_final_requirement_text():
    # Integration-style check between the two pure functions: the combined
    # output must always be valid, well-formed ADF - never raise, never
    # produce an empty content list for non-empty input.
    text = format_final_requirement_text(_make_final_requirement())
    doc = plain_text_to_adf(text)
    assert doc["type"] == "doc"
    assert len(doc["content"]) > 0
    node_types = {node["type"] for node in doc["content"]}
    assert node_types <= {"paragraph", "bulletList"}


# --- app/jira/client.py: update_issue ------------------------------------------


def test_update_issue_sends_description_only(monkeypatch):
    store.save_connection(_make_connection())
    captured: dict = {}

    def _fake_put(url, headers=None, json=None, **kwargs):
        captured["url"] = url
        captured["json"] = json
        return httpx.Response(204, request=httpx.Request("PUT", url))

    monkeypatch.setattr(client.httpx, "put", _fake_put)

    client.update_issue("PROJ-1", _make_final_requirement())

    assert captured["url"].endswith("/issue/PROJ-1")
    # MVP scope: description is the only field ever sent.
    assert set(captured["json"]["fields"].keys()) == {"description"}
    assert captured["json"]["fields"]["description"]["type"] == "doc"


def test_update_issue_includes_all_requirement_sections_in_description(monkeypatch):
    store.save_connection(_make_connection())
    captured: dict = {}

    def _fake_put(url, headers=None, json=None, **kwargs):
        captured["json"] = json
        return httpx.Response(204, request=httpx.Request("PUT", url))

    monkeypatch.setattr(client.httpx, "put", _fake_put)

    client.update_issue("PROJ-1", _make_final_requirement(user_story="As a manager, I want CSV export."))

    adf_text = json_module.dumps(captured["json"]["fields"]["description"])
    assert "As a manager, I want CSV export." in adf_text
    assert "Given A, when B, then C." in adf_text
    assert "In scope: X." in adf_text
    assert "Assumes Y exists." in adf_text
    assert "Depends on Z." in adf_text


def test_update_issue_not_connected_raises_without_http_call(monkeypatch):
    def _fail_if_called(*args, **kwargs):
        raise AssertionError("httpx.put must not be called when Jira is not connected")

    monkeypatch.setattr(client.httpx, "put", _fail_if_called)

    with pytest.raises(JiraNotConnectedError):
        client.update_issue("PROJ-1", _make_final_requirement())


def test_update_issue_http_failure_raises_jira_api_error(monkeypatch):
    store.save_connection(_make_connection())

    def _fake_put(url, headers=None, json=None, **kwargs):
        return httpx.Response(400, json={"errorMessages": ["bad request"]}, request=httpx.Request("PUT", url))

    monkeypatch.setattr(client.httpx, "put", _fake_put)

    with pytest.raises(JiraAPIError):
        client.update_issue("PROJ-1", _make_final_requirement())


# --- app/jira/router.py: POST /api/jira/issues/{issue_key}/update -------------


def test_jira_update_issue_not_connected_returns_401():
    response = client_app.post(
        "/api/jira/issues/PROJ-1/update", json=_make_final_requirement().model_dump()
    )
    assert response.status_code == 401


def test_jira_update_issue_success(monkeypatch):
    store.save_connection(_make_connection())
    captured: dict = {}

    def _fake_update_issue(issue_key, final_requirement):
        captured["issue_key"] = issue_key
        captured["final_requirement"] = final_requirement

    monkeypatch.setattr("app.jira.router.client.update_issue", _fake_update_issue)

    response = client_app.post(
        "/api/jira/issues/PROJ-1/update", json=_make_final_requirement().model_dump()
    )

    assert response.status_code == 200
    assert response.json() == {"issue_key": "PROJ-1", "updated": True}
    assert captured["issue_key"] == "PROJ-1"
    assert captured["final_requirement"] == _make_final_requirement()


def test_jira_update_issue_api_failure_returns_502(monkeypatch):
    store.save_connection(_make_connection())

    def _raise(issue_key, final_requirement):
        raise JiraAPIError("upstream failure")

    monkeypatch.setattr("app.jira.router.client.update_issue", _raise)

    response = client_app.post(
        "/api/jira/issues/PROJ-1/update", json=_make_final_requirement().model_dump()
    )
    assert response.status_code == 502


def test_jira_update_issue_rejects_missing_body():
    store.save_connection(_make_connection())
    response = client_app.post("/api/jira/issues/PROJ-1/update", json={})
    assert response.status_code == 422


# --- app/analysis/schemas.py: TicketInput.source_issue_key --------------------


def test_ticket_input_source_issue_key_defaults_to_none():
    ticket = TicketInput(title="T", description="D")
    assert ticket.source_issue_key is None


def test_ticket_input_source_issue_key_roundtrips():
    ticket = TicketInput(title="T", description="D", source_issue_key="PROJ-1")
    assert ticket.source_issue_key == "PROJ-1"
    assert ticket.model_dump()["source_issue_key"] == "PROJ-1"


# --- app/agent/prompts.py: related_issues wiring ------------------------------
#
# Deterministic prompt-construction tests, mirroring
# tests/test_rag_integration.py's build_user_prompt coverage for
# retrieved_context - same "optional, backward-compatible, additive
# section" pattern (docs/skills.md section 9), now for Jira-confirmed
# relationships instead of RAG context.


def test_build_user_prompt_includes_related_issues_section_when_present():
    ticket = TicketInput(
        title="Add push notification support",
        description="Send push notifications to mobile devices.",
        related_issues=[
            RelatedIssue(key="PROJ-101", relationship="blocks", summary="Create Notification API"),
            RelatedIssue(key="PROJ-102", relationship="relates to", summary=None),
        ],
    )

    prompt = build_user_prompt(ticket)

    assert "Related Jira issues (confirmed by Jira, not inferred):" in prompt
    assert "PROJ-101 (blocks): Create Notification API" in prompt
    assert "PROJ-102 (relates to)" in prompt


def test_build_user_prompt_omits_related_issues_section_when_none():
    ticket = TicketInput(title="T", description="D", related_issues=None)
    prompt = build_user_prompt(ticket)
    assert "Related Jira issues" not in prompt


def test_build_user_prompt_omits_related_issues_section_when_empty_list():
    ticket = TicketInput(title="T", description="D", related_issues=[])
    prompt = build_user_prompt(ticket)
    assert "Related Jira issues" not in prompt


def test_build_user_prompt_default_call_shape_still_unaffected_by_related_issues():
    # Same call shape as every pre-Jira caller (manual ticket entry): no
    # related_issues field set at all. Must behave exactly as before.
    ticket = TicketInput(title="T", description="D")
    prompt = build_user_prompt(ticket)
    assert "Related Jira issues" not in prompt
