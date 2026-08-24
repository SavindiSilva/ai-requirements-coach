"""Anthropic Claude client wrappers for the coaching workflow's LLM calls.

Structured output is enforced via forced tool-use, mirroring
app/agent/llm.py: Claude is given exactly one tool whose input_schema is
generated from a Pydantic model, and `tool_choice` forces Claude to call it.
The tool's `input` is then re-validated through the same Pydantic model, so
no natural-language parsing occurs.

Phase 2A uses this for the clarification-question step; Phase 2E reuses the
same pattern for the final-requirement generation step.

Phase 2E addition: for a ticket that goes through 5 rounds of genuinely
uninformative coaching answers (stop_reason max_questions_reached), Claude
occasionally returns a malformed submit_final_requirement call - observed in
production as a list-typed field (e.g. acceptance_criteria) collapsed into a
single string, with user_story omitted. generate_final_requirement()
recovers these two specific, recoverable shapes via
normalize_final_requirement_input() before validation, logging whenever it
fires, rather than hard-failing finalize outright. See docs/skills.md for
the pattern.
"""

import logging

from app.agent.llm import get_client
from app.coaching.schemas import ClarificationQuestionOutput, FinalRequirementContent
from app.core.config import settings

logger = logging.getLogger(__name__)

QUESTION_TOOL_NAME = "submit_clarification_question"

_QUESTION_TOOL = {
    "name": QUESTION_TOOL_NAME,
    "description": "Submit a single focused clarification question and an explanation of why it matters.",
    "input_schema": ClarificationQuestionOutput.model_json_schema(),
}

FINAL_REQUIREMENT_TOOL_NAME = "submit_final_requirement"

_FINAL_REQUIREMENT_TOOL = {
    "name": FINAL_REQUIREMENT_TOOL_NAME,
    "description": "Submit the complete structured, development-ready requirement.",
    "input_schema": FinalRequirementContent.model_json_schema(),
}


class CoachingLLMError(RuntimeError):
    """Raised when Claude fails to produce a valid clarification question."""


def generate_clarification_question(system_prompt: str, user_prompt: str) -> ClarificationQuestionOutput:
    client = get_client()

    try:
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=1024,
            system=system_prompt,
            tools=[_QUESTION_TOOL],
            tool_choice={"type": "tool", "name": QUESTION_TOOL_NAME},
            messages=[{"role": "user", "content": user_prompt}],
        )
    except Exception as exc:
        raise CoachingLLMError(f"Claude API call failed: {exc}") from exc

    for block in response.content:
        if block.type == "tool_use" and block.name == QUESTION_TOOL_NAME:
            try:
                return ClarificationQuestionOutput.model_validate(block.input)
            except Exception as exc:
                raise CoachingLLMError(f"Claude returned invalid structured output: {exc}") from exc

    raise CoachingLLMError("Claude did not return the expected tool_use block.")


_FINAL_REQUIREMENT_LIST_FIELDS = ("acceptance_criteria", "scope", "assumptions", "dependencies")


def normalize_final_requirement_input(raw: dict, *, ticket_title: str, session_id: str) -> dict:
    """Coerce a small set of recoverable malformed shapes in Claude's raw
    submit_final_requirement input into valid FinalRequirementContent input.

    Only two shapes are recovered, both observed in production for tickets
    that reach max_questions_reached with genuinely uninformative coaching
    answers - there is nothing safe to guess for any other malformed shape,
    so anything else is left as-is for Pydantic to reject normally:

    - A list-typed field (acceptance_criteria/scope/assumptions/dependencies)
      returned as a non-empty string: wrapped as a single-item list,
      preserving Claude's actual text rather than discarding it.
    - A missing or blank user_story: replaced with an honest, clearly
      incomplete placeholder built from the ticket title - never fabricated
      content, just a statement that coaching didn't fully resolve it.

    Pure and side-effect-free except for the log line noting when/what fired,
    so this can be unit tested directly with hand-built malformed dicts (no
    LLM call needed), and so real occurrences stay visible rather than being
    silently patched over.
    """
    normalized = dict(raw)

    for field in _FINAL_REQUIREMENT_LIST_FIELDS:
        value = normalized.get(field)
        if isinstance(value, str) and value.strip():
            logger.warning(
                "generate_final_requirement: coercing %r from a string to a single-item list "
                "(session_id=%s)",
                field,
                session_id,
            )
            normalized[field] = [value]

    user_story = normalized.get("user_story")
    if not isinstance(user_story, str) or not user_story.strip():
        logger.warning(
            "generate_final_requirement: user_story missing/blank, substituting a fallback "
            "(session_id=%s)",
            session_id,
        )
        normalized["user_story"] = (
            f"As a user, I want {ticket_title}, though this requirement was not fully "
            "clarified during coaching."
        )

    return normalized


def generate_final_requirement(
    system_prompt: str, user_prompt: str, *, ticket_title: str, session_id: str
) -> FinalRequirementContent:
    client = get_client()

    try:
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=4096,
            system=system_prompt,
            tools=[_FINAL_REQUIREMENT_TOOL],
            tool_choice={"type": "tool", "name": FINAL_REQUIREMENT_TOOL_NAME},
            messages=[{"role": "user", "content": user_prompt}],
        )
    except Exception as exc:
        raise CoachingLLMError(f"Claude API call failed: {exc}") from exc

    for block in response.content:
        if block.type == "tool_use" and block.name == FINAL_REQUIREMENT_TOOL_NAME:
            normalized_input = normalize_final_requirement_input(
                block.input, ticket_title=ticket_title, session_id=session_id
            )
            try:
                return FinalRequirementContent.model_validate(normalized_input)
            except Exception as exc:
                raise CoachingLLMError(f"Claude returned invalid structured output: {exc}") from exc

    raise CoachingLLMError("Claude did not return the expected tool_use block.")
