"""Pydantic schemas for the Phase 1 single-shot requirement analysis.

`AnalysisContent` is the exact shape Claude is asked to fill in via forced
tool-use — it deliberately excludes `overall_readiness`, which is computed
in code from the four criterion scores rather than trusted from the LLM.
`AnalysisResult` is the full API response shape (`AnalysisContent` plus the
computed `overall_readiness`).
"""

from pydantic import BaseModel, Field


class RelatedIssue(BaseModel):
    """A Jira-confirmed relationship to another issue (link, parent, or subtask).

    Distinct from `AnalysisContent.possible_dependencies`, which is only ever
    LLM-inferred from ticket text and never confirmed. A `RelatedIssue` comes
    directly from Jira's own relationship data (see CLAUDE.md section 13) -
    it is never invented or inferred.
    """

    key: str = Field(..., min_length=1)
    relationship: str = Field(..., min_length=1, description="e.g. 'blocks', 'is blocked by', 'relates to', 'parent', 'subtask'.")
    summary: str | None = None


class TicketInput(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    related_issues: list[RelatedIssue] | None = Field(
        default=None,
        description="Optional Jira-confirmed relationships. None for tickets entered manually.",
    )
    source_issue_key: str | None = Field(
        default=None,
        description="The Jira issue key this ticket was imported from, if any. None for tickets entered manually. Lets /finalize know which Jira issue an approved update should write back to.",
    )
    project_id: str | None = Field(
        default=None,
        description="The Jira project this ticket belongs to, if imported from Jira. Scopes RAG "
        "knowledge retrieval (app/rag/store.py) to that project's uploaded documents. None for "
        "tickets entered manually, in which case retrieval falls back to "
        "app/agent/rag_integration.py's TEMP_EVAL_PROJECT_ID.",
    )


class CriterionScore(BaseModel):
    score: int = Field(..., ge=0, le=3, description="0-3 per the Definition-of-Ready rubric.")
    evidence: str = Field(..., min_length=1, description="Concrete evidence from the ticket text justifying the score.")


class ClarificationQuestion(BaseModel):
    question: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1, description="Why this question matters / what gap it resolves.")


class AnalysisContent(BaseModel):
    requirement_clarity: CriterionScore
    acceptance_criteria: CriterionScore
    open_questions: CriterionScore
    scope_definition: CriterionScore

    what_is_clear: list[str] = Field(default_factory=list)
    what_is_missing: list[str] = Field(default_factory=list)
    what_is_ambiguous: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    possible_dependencies: list[str] = Field(
        default_factory=list,
        description="Dependencies inferred from ticket text only. Never confirmed — no Jira data is available in Phase 1.",
    )
    scope_problems: list[str] = Field(default_factory=list)
    missing_acceptance_criteria: list[str] = Field(default_factory=list)
    important_open_questions: list[str] = Field(default_factory=list)
    clarification_questions: list[ClarificationQuestion] = Field(default_factory=list)


class AnalysisResult(AnalysisContent):
    overall_readiness: float = Field(..., ge=0, le=3)
