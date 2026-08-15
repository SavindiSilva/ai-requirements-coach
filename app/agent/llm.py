"""Anthropic Claude client wrapper that enforces structured output.

Structured output is enforced via forced tool-use: Claude is given exactly
one tool whose input_schema is generated from `AnalysisContent`, and
`tool_choice` forces Claude to call it. The tool's `input` is then
re-validated through the same Pydantic model, so we never parse or trust
arbitrary natural-language text.
"""

from anthropic import Anthropic

from app.analysis.schemas import AnalysisContent
from app.core.config import settings

ANALYSIS_TOOL_NAME = "submit_requirement_analysis"

_ANALYSIS_TOOL = {
    "name": ANALYSIS_TOOL_NAME,
    "description": "Submit the complete structured Definition-of-Ready analysis for the ticket.",
    "input_schema": AnalysisContent.model_json_schema(),
}

_client: Anthropic | None = None


def get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


class LLMAnalysisError(RuntimeError):
    """Raised when Claude fails to produce a valid structured analysis."""


def run_structured_analysis(system_prompt: str, user_prompt: str) -> AnalysisContent:
    client = get_client()

    try:
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=4096,
            system=system_prompt,
            tools=[_ANALYSIS_TOOL],
            tool_choice={"type": "tool", "name": ANALYSIS_TOOL_NAME},
            messages=[{"role": "user", "content": user_prompt}],
        )
    except Exception as exc:
        raise LLMAnalysisError(f"Claude API call failed: {exc}") from exc

    for block in response.content:
        if block.type == "tool_use" and block.name == ANALYSIS_TOOL_NAME:
            try:
                return AnalysisContent.model_validate(block.input)
            except Exception as exc:
                raise LLMAnalysisError(f"Claude returned invalid structured output: {exc}") from exc

    raise LLMAnalysisError("Claude did not return the expected tool_use block.")
