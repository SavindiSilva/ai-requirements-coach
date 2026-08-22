"""Pydantic schemas for Jira API responses.

`RelatedIssue` is intentionally reused from app.analysis.schemas rather than
duplicated here - it is the exact same "Jira-confirmed relationship" shape
whether it appears embedded in a fetched issue or on TicketInput, so one
model serves both (see CLAUDE.md section 30: reuse existing schemas, don't
create duplicate/parallel ones).
"""

from pydantic import BaseModel, Field

from app.analysis.schemas import RelatedIssue

__all__ = [
    "RelatedIssue",
    "JiraStatusResponse",
    "JiraProject",
    "JiraIssueSummary",
    "JiraIssueDetail",
    "JiraUpdateResponse",
]


class JiraStatusResponse(BaseModel):
    connected: bool


class JiraProject(BaseModel):
    id: str
    key: str
    name: str


class JiraIssueSummary(BaseModel):
    key: str
    summary: str
    status: str = Field(..., description="Jira's own workflow status - kept separate from AI review status (CLAUDE.md section 16).")
    issue_type: str


class JiraIssueDetail(JiraIssueSummary):
    description: str
    links: list[RelatedIssue] = Field(default_factory=list)


class JiraUpdateResponse(BaseModel):
    issue_key: str
    updated: bool = True
