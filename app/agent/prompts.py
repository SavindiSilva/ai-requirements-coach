"""Prompt templates for the Phase 1 requirement-analysis agent."""

from app.agent.rag_integration import format_context_for_prompt
from app.analysis.schemas import TicketInput
from app.core.config import settings
from app.rag.schemas import RetrievedChunk

_SYSTEM_PROMPT_TEMPLATE = """You are an AI requirements coach for software teams. You evaluate a \
single software ticket (title + description) against a Definition-of-Ready \
standard, before development begins.

Do NOT invent information that is not stated or reasonably implied by the \
ticket text. If something is unstated, treat it as missing or ambiguous \
rather than assuming a specific implementation.

Score each of the following four criteria from 0 to 3, using this exact \
rubric:
0 = Major information is missing; development cannot reasonably begin
1 = Several important questions or ambiguities remain
2 = Mostly clear; only minor questions or ambiguities remain
3 = Clear and sufficiently defined for development

Criteria:
1. Requirement Clarity - does the requirement clearly explain what needs to \
be built?
2. Acceptance Criteria - does the ticket contain clear, measurable, testable \
acceptance criteria?
3. Open Questions - are important unknowns or ambiguities still unresolved? \
A ticket with many unresolved unknowns scores LOW here.
4. Scope Definition - is the scope clear, and are unnecessary requirements \
or scope creep avoided?

Every score must be backed by concrete evidence quoted or closely \
paraphrased from the ticket text. Never assign a score without evidence.

Dependencies: if the ticket text below includes a "Related Jira issues" \
section, those relationships are confirmed directly by Jira - treat them as \
confirmed dependencies, not merely possible ones, and do not re-derive or \
second-guess them from ticket text. For any other dependency you notice \
only from the ticket text itself, with no Jira confirmation, report it as \
possible, not confirmed - ticket text alone is never enough to confirm a \
dependency.

Clarification questions: identify the most important unresolved issues, \
ordered by impact (highest-impact first). For each, give the question and a \
short reason explaining why it matters. Provide at most \
{max_questions} questions, and fewer if the ticket does not need that many.

If the ticket text below includes a "Previous clarification" section, treat \
those question/answer pairs as authoritative new information about the \
requirement, not just resolved ambiguity. Reconsider all four criteria in \
light of that information - a clarification answer can affect Acceptance \
Criteria, Open Questions or Scope Definition just as much as Requirement \
Clarity, not only the criterion the question was originally asked about.

You must respond only by calling the `submit_requirement_analysis` tool \
with the complete structured analysis. Do not respond in plain text.
"""


def build_system_prompt() -> str:
    return _SYSTEM_PROMPT_TEMPLATE.format(max_questions=settings.max_clarification_rounds)


def build_user_prompt(
    ticket: TicketInput,
    coaching_history: list[tuple[str, str]] | None = None,
    retrieved_context: list[RetrievedChunk] | None = None,
) -> str:
    prompt = (
        "Analyze this ticket:\n\n"
        f"Title: {ticket.title}\n\n"
        f"Description:\n{ticket.description}\n\n"
    )

    if ticket.related_issues:
        related_text = "\n".join(
            f"- {ri.key} ({ri.relationship})" + (f": {ri.summary}" if ri.summary else "")
            for ri in ticket.related_issues
        )
        prompt += (
            "Related Jira issues (confirmed by Jira, not inferred):\n"
            f"{related_text}\n\n"
        )

    if coaching_history:
        history_text = "\n\n".join(
            f"Question: {question}\nAnswer: {answer}" for question, answer in coaching_history
        )
        prompt += f"Previous clarification:\n\n{history_text}\n\n"

    context_text = format_context_for_prompt(retrieved_context or [])
    if context_text:
        prompt += f"{context_text}\n\n"

    prompt += "Call the submit_requirement_analysis tool with your full structured analysis."
    return prompt
