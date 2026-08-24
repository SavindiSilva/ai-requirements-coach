"""Pydantic schemas for the reviewed-ticket history.

`ReviewedTicket` mirrors frontend/src/lib/types/reviewedTicket.ts (kept in
sync by hand, same convention as every other frontend/backend schema pair
in this codebase - see docs/skills.md section 2).
"""

from pydantic import BaseModel, Field


class ReviewedTicket(BaseModel):
    issue_key: str | None = Field(
        default=None,
        description="The Jira issue key this ticket was reviewed from, if any. Used to upsert "
        "by ticket (see app/tickets/store.py) rather than recording a duplicate row when the "
        "same ticket is reviewed again after coaching finishes.",
    )
    title: str = Field(..., min_length=1)
    readiness: float = Field(..., ge=0, le=3)
    reviewed_at: float = Field(..., description="Client-supplied timestamp (ms since epoch) when this ticket was recorded.")
    stop_reason: str | None = Field(
        default=None,
        description="Coaching's stop_reason once coaching has finished; None if only analysed so far.",
    )
