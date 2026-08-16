"""Prompt templates for the Phase 2A coaching clarification-question step."""

from app.analysis.schemas import AnalysisResult, TicketInput
from app.coaching.selection import CRITERION_LABELS

_SYSTEM_PROMPT = """You are an AI requirements coach for software teams. You have \
already analysed a ticket against a four-criterion Definition-of-Ready rubric \
(Requirement Clarity, Acceptance Criteria, Open Questions, Scope Definition), \
scored 0-3 each.

Your job now is to ask exactly ONE focused clarification question about the \
single weakest criterion for this ticket, based only on the analysis findings \
you are given below. Do not invent issues that are not present in those \
findings, and do not ask about other criteria.

The question should:
- Target the single most important unresolved issue for that criterion.
- Be specific and directly answerable by the person who owns the ticket.

Also provide a short "why" explanation describing why this question matters \
for moving the requirement toward development-ready.

You must respond only by calling the `submit_clarification_question` tool \
with the `question` and `why` fields. Do not respond in plain text.
"""


def build_question_system_prompt() -> str:
    return _SYSTEM_PROMPT


def build_question_user_prompt(
    ticket: TicketInput,
    analysis: AnalysisResult,
    criterion_key: str,
    issues: list[str],
    previous_questions: list[str] | None = None,
) -> str:
    criterion = getattr(analysis, criterion_key)
    label = CRITERION_LABELS[criterion_key]
    issues_text = "\n".join(f"- {issue}" for issue in issues) or "- (no specific findings listed)"

    previous_text = ""
    if previous_questions:
        previous_list = "\n".join(f"- {question}" for question in previous_questions)
        previous_text = (
            "Questions already asked and answered earlier in this coaching "
            f"session (do not repeat these or ask something that overlaps "
            f"with them):\n{previous_list}\n\n"
        )

    return (
        "Ticket:\n"
        f"Title: {ticket.title}\n\n"
        f"Description:\n{ticket.description}\n\n"
        f"Weakest criterion: {label} (score {criterion.score}/3)\n"
        f"Evidence for this score: {criterion.evidence}\n\n"
        f"Findings related to this criterion:\n{issues_text}\n\n"
        f"{previous_text}"
        "Call the submit_clarification_question tool with ONE focused question "
        "and a short why explanation targeting the most important unresolved "
        "issue above."
    )
