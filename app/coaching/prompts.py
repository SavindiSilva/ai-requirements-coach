"""Prompt templates for the coaching workflow.

Phase 2A: the clarification-question step. Phase 2E: the final-requirement
generation step, once coaching has been marked complete.
"""

from app.agent.rag_integration import format_context_for_prompt
from app.analysis.schemas import AnalysisResult, TicketInput
from app.coaching.selection import CRITERION_LABELS, CRITERION_PRIORITY
from app.rag.schemas import RetrievedChunk

_SYSTEM_PROMPT = """You are an AI requirements coach for software teams. You have \
already analysed a ticket against a four-criterion Definition-of-Ready rubric \
(Requirement Clarity, Acceptance Criteria, Open Questions, Scope Definition), \
scored 0-3 each.

Your job now is to ask exactly ONE focused clarification question about the \
single weakest criterion for this ticket, based only on the analysis findings \
you are given below. Do not invent issues that are not present in those \
findings, and do not ask about other criteria.

Your audience is a Product Manager or Business Analyst, not an engineer. \
Write for that reader:
- Use plain, everyday words. Avoid technical jargon (e.g. say "how the app \
should behave" instead of "system behavior", "what should trigger it" \
instead of "the triggering event/condition") unless the ticket itself \
already uses that technical term.
- Ask about exactly ONE thing. If you are tempted to use "and", split it \
into a single question about the single most important issue.
- Keep the question to one short sentence.
- If the natural question would otherwise list multiple technical options \
in one sentence (e.g. "by API key, account, or IP address?"), do not just \
simplify the wording around that list - restructure the question instead. \
Either (a) ask directly about the single most likely/important option \
("Should this apply per user, rather than per device or location?"), or \
(b) ask what the person actually needs to decide, in plain terms, without \
naming the technical option list.

The question should:
- Target the single most important unresolved issue for that criterion.
- Be specific and directly answerable by the person who owns the ticket - \
avoid vague generic questions that could apply to any ticket.

Also provide a "why" explanation: exactly ONE short, plain-language \
sentence, written for a non-technical reader, explaining why THIS \
specific answer matters. Ground it in the specific gap named above - do \
not fall back on a generic, boilerplate reason that could apply to any \
ticket (e.g. avoid stock phrasing like "so the team can build/test it \
correctly"). Do not use multiple clauses stacked with commas/semicolons, \
and do not reference the rubric, criteria names, or scores.

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


_FINALIZE_SYSTEM_PROMPT = """You are an AI requirements coach for software teams. A coaching \
conversation has just concluded for a ticket you previously analysed against \
a four-criterion Definition-of-Ready rubric (Requirement Clarity, Acceptance \
Criteria, Open Questions, Scope Definition). Your job now is to synthesise \
the original ticket plus everything learned during coaching into a single \
development-ready requirement.

Genuinely incorporate the clarification answers - do not simply paraphrase \
the original ticket text. For example, if the original ticket said "add \
notifications when something happens" and coaching resolved the trigger \
event to "a new message is received", the final requirement must state that \
resolved trigger explicitly, not the original vague phrase.

Do not invent information that was not stated in the ticket, the analysis \
findings, or the coaching answers.

Produce exactly these fields by calling the submit_final_requirement tool:

- user_story: one clear sentence naming who wants what and why.
- acceptance_criteria: specific, measurable, testable conditions. Prefer \
Given/When/Then phrasing where it fits naturally.
- scope: what is included, informed by the scope findings below. Do not \
reintroduce scope problems the analysis already flagged.
- assumptions: only assumptions that remain relevant after coaching - if a \
coaching answer already resolved an assumption, do not repeat it here.
- dependencies: only dependencies carried over from the analysis findings \
below. Never invent a new dependency. These were never confirmed by Jira \
data, so phrase each one as inferred/possible (e.g. "Likely depends on ..."), \
never as a confirmed fact.

You must respond only by calling the submit_final_requirement tool with the \
complete structured requirement. Do not respond in plain text.
"""


def build_finalize_system_prompt() -> str:
    return _FINALIZE_SYSTEM_PROMPT


def build_finalize_user_prompt(
    ticket: TicketInput,
    analysis: AnalysisResult,
    coaching_history: list[tuple[str, str]],
    stop_reason: str | None,
    retrieved_context: list[RetrievedChunk] | None = None,
) -> str:
    scores_text = "\n".join(
        f"- {CRITERION_LABELS[key]}: {getattr(analysis, key).score}/3 "
        f"(evidence: {getattr(analysis, key).evidence})"
        for key in CRITERION_PRIORITY
    )

    history_text = "\n\n".join(
        f"Question: {question}\nAnswer: {answer}" for question, answer in coaching_history
    ) or "(no coaching questions were asked)"

    def _list_or_none(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items) or "- (none)"

    if stop_reason == "max_questions_reached":
        stop_reason_text = (
            "Coaching status: the maximum number of clarification questions was "
            "reached before every criterion met the readiness bar. Some areas may "
            "still be unresolved. Produce your best current draft, but do not "
            "represent any unresolved area as a confirmed, settled fact - keep "
            "assumptions and scope honest about what is still actually known."
        )
    else:
        stop_reason_text = (
            "Coaching status: all four readiness criteria met the readiness bar. "
            "Generate the final requirement normally."
        )

    context_text = format_context_for_prompt(retrieved_context or [])
    context_block = f"{context_text}\n\n" if context_text else ""

    return (
        "Ticket:\n"
        f"Title: {ticket.title}\n\n"
        f"Description:\n{ticket.description}\n\n"
        f"Latest readiness scores:\n{scores_text}\n\n"
        f"Missing-information findings:\n{_list_or_none(analysis.what_is_missing)}\n\n"
        f"Missing acceptance-criteria findings:\n{_list_or_none(analysis.missing_acceptance_criteria)}\n\n"
        f"Scope findings:\n{_list_or_none(analysis.scope_problems)}\n\n"
        f"Possible dependencies (never confirmed - only Jira could confirm these):\n"
        f"{_list_or_none(analysis.possible_dependencies)}\n\n"
        f"Remaining assumptions:\n{_list_or_none(analysis.assumptions)}\n\n"
        f"Coaching question/answer history:\n{history_text}\n\n"
        f"{stop_reason_text}\n\n"
        f"{context_block}"
        "Call the submit_final_requirement tool with the complete structured "
        "development-ready requirement."
    )
