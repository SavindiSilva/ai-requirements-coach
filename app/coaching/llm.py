"""Anthropic Claude client wrapper for the Phase 2A clarification-question step.

Structured output is enforced via forced tool-use, mirroring
app/agent/llm.py: Claude is given exactly one tool whose input_schema is
generated from `ClarificationQuestionOutput`, and `tool_choice` forces
Claude to call it. The tool's `input` is then re-validated through the same
Pydantic model, so no natural-language parsing occurs.
"""

from app.agent.llm import get_client
from app.coaching.schemas import ClarificationQuestionOutput
from app.core.config import settings

QUESTION_TOOL_NAME = "submit_clarification_question"

_QUESTION_TOOL = {
    "name": QUESTION_TOOL_NAME,
    "description": "Submit a single focused clarification question and an explanation of why it matters.",
    "input_schema": ClarificationQuestionOutput.model_json_schema(),
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
