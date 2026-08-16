"""Anthropic Claude client wrappers for the coaching workflow's LLM calls.

Structured output is enforced via forced tool-use, mirroring
app/agent/llm.py: Claude is given exactly one tool whose input_schema is
generated from a Pydantic model, and `tool_choice` forces Claude to call it.
The tool's `input` is then re-validated through the same Pydantic model, so
no natural-language parsing occurs.

Phase 2A uses this for the clarification-question step; Phase 2E reuses the
same pattern for the final-requirement generation step.
"""

from app.agent.llm import get_client
from app.coaching.schemas import ClarificationQuestionOutput, FinalRequirementContent
from app.core.config import settings

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


def generate_final_requirement(system_prompt: str, user_prompt: str) -> FinalRequirementContent:
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
            try:
                return FinalRequirementContent.model_validate(block.input)
            except Exception as exc:
                raise CoachingLLMError(f"Claude returned invalid structured output: {exc}") from exc

    raise CoachingLLMError("Claude did not return the expected tool_use block.")
