"""Pydantic schemas for the Phase 2A coaching-start endpoint.

`ClarificationQuestionOutput` is the exact shape Claude is asked to fill in
via forced tool-use for the coaching question step, mirroring the
`AnalysisContent` pattern in app/analysis/schemas.py.
"""

from pydantic import BaseModel, Field, field_validator


class ClarificationQuestionOutput(BaseModel):
    question: str = Field(..., min_length=1)
    why: str = Field(..., min_length=1, description="Why this question matters / what gap it resolves.")


class CurrentScores(BaseModel):
    requirement_clarity: int = Field(..., ge=0, le=3)
    acceptance_criteria: int = Field(..., ge=0, le=3)
    open_questions: int = Field(..., ge=0, le=3)
    scope_definition: int = Field(..., ge=0, le=3)


class CoachingStartResponse(BaseModel):
    session_id: str
    question: str
    why: str
    current_scores: CurrentScores


class MessageRequest(BaseModel):
    answer: str = Field(..., min_length=1)

    @field_validator("answer")
    @classmethod
    def answer_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("answer must not be empty or whitespace-only")
        return v


class CoachingMessageResponse(BaseModel):
    session_id: str
    question: str
    answer: str
    question_count: int
    questions_asked: list[str]
    answers: list[str]
    current_scores: CurrentScores
