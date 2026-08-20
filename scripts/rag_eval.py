"""Manual, non-CI script: with-RAG vs. without-RAG evaluation for Phase 3.

Not a pytest test - judging whether RAG made an analysis meaningfully
better is a human call, not something to assert automatically given
Claude's output is non-deterministic. Run manually:

    python scripts/rag_eval.py

Seeds a few representative documents into the temporary Phase 3 evaluation
project scope (project_id="default" - see app/agent/rag_integration.py and
CLAUDE.md section 7, "Temporary evaluation scope"), then runs a handful of
representative, deliberately vague tickets through requirement analysis
twice: once with retrieved project context included in the prompt, once
without. Prints both analyses side by side so a human can compare gap
findings, scores, and clarification questions.

Requires ANTHROPIC_API_KEY (for analysis) and OPENAI_API_KEY (for
embeddings) to be configured. Without OPENAI_API_KEY, seeding will fail and
RAG retrieval will fail safe to no context on both runs - the script warns
about this rather than silently producing a no-op comparison.

Note: each run seeds new documents with fresh random document_ids into the
persistent ChromaDB store (chroma_data/), so repeated runs accumulate
duplicate copies of the same seed documents under project_id="default".
That's expected for a manual, repeatable eval script - it doesn't affect
correctness, only means retrieved top-k chunks may include near-duplicates
after several runs.
"""

import sys

from app.agent.llm import run_structured_analysis
from app.agent.prompts import build_system_prompt, build_user_prompt
from app.agent.rag_integration import TEMP_EVAL_PROJECT_ID, get_retrieved_context
from app.analysis.schemas import TicketInput
from app.core.config import settings
from app.rag.embeddings import EmbeddingError
from app.rag.schemas import DocumentInput, DocumentType
from app.rag.store import RAGStoreError, add_document

SEED_DOCUMENTS = [
    DocumentInput(
        project_id=TEMP_EVAL_PROJECT_ID,
        document_type=DocumentType.PRODUCT_RULE,
        title="Refund Policy",
        text=(
            "Refunds over $500 require manager approval before being processed. "
            "All approved refunds must be issued to the original payment method "
            "within 5 business days. Refund requests older than 90 days from the "
            "original purchase date are not eligible."
        ),
    ),
    DocumentInput(
        project_id=TEMP_EVAL_PROJECT_ID,
        document_type=DocumentType.ENGINEERING_GUIDELINE,
        title="API Endpoint Standards",
        text=(
            "All new API endpoints must be idempotent under retry. Every endpoint "
            "must return structured error responses following the standard "
            "{error_code, message} schema, and must never return a bare 500 "
            "without a machine-readable error_code."
        ),
    ),
    DocumentInput(
        project_id=TEMP_EVAL_PROJECT_ID,
        document_type=DocumentType.DEFINITION_OF_READY,
        title="Definition of Ready",
        text=(
            "A ticket is ready for development when acceptance criteria are "
            "written in Given/When/Then format, the scope explicitly states what "
            "is out of scope, and no open questions remain unresolved."
        ),
    ),
]

EVAL_TICKETS = [
    TicketInput(
        title="Add refund feature",
        description="Users should be able to request a refund for their order.",
    ),
    TicketInput(
        title="Add order export API endpoint",
        description="Add an endpoint so partners can export their order history.",
    ),
]


def _seed_documents() -> None:
    print(f"Seeding {len(SEED_DOCUMENTS)} document(s) into project_id={TEMP_EVAL_PROJECT_ID!r}...")
    for doc in SEED_DOCUMENTS:
        try:
            result = add_document(doc)
            print(f"  - {doc.title!r}: {result.chunk_count} chunk(s), document_id={result.document_id}")
        except (EmbeddingError, RAGStoreError) as exc:
            print(f"  - FAILED to seed {doc.title!r}: {exc}")


def _run_analysis(ticket: TicketInput, use_rag: bool):
    retrieved_context = []
    if use_rag:
        query_text = f"{ticket.title}\n{ticket.description}"
        retrieved_context = get_retrieved_context(query_text, project_id=TEMP_EVAL_PROJECT_ID)

    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(ticket, retrieved_context=retrieved_context)
    content = run_structured_analysis(system_prompt, user_prompt)

    scores = {
        "requirement_clarity": content.requirement_clarity.score,
        "acceptance_criteria": content.acceptance_criteria.score,
        "open_questions": content.open_questions.score,
        "scope_definition": content.scope_definition.score,
    }
    overall = round(sum(scores.values()) / 4, 2)
    return retrieved_context, scores, overall, content


def _print_result(label, retrieved_context, scores, overall, content) -> None:
    print(f"\n--- {label} ---")
    print(f"Retrieved chunks: {len(retrieved_context)}")
    for chunk in retrieved_context:
        print(
            f"  - [{chunk.metadata.document_type.value}] {chunk.metadata.title} "
            f"(distance={chunk.distance:.3f})"
        )
    print(f"Scores: {scores}  |  Overall readiness: {overall}")
    print("Missing:", content.what_is_missing)
    print("Missing acceptance criteria:", content.missing_acceptance_criteria)
    print("Clarification questions:")
    for q in content.clarification_questions:
        print(f"  - {q.question}")


def main() -> None:
    if not settings.anthropic_api_key:
        print("ANTHROPIC_API_KEY is not configured - cannot run analysis. Aborting.")
        sys.exit(1)
    if not settings.openai_api_key:
        print(
            "WARNING: OPENAI_API_KEY is not configured. Seeding will fail and RAG "
            "retrieval will fail safe to no context on the 'with RAG' run too, so "
            "both runs below will end up identical - this does not demonstrate a "
            "with/without difference. Configure OPENAI_API_KEY for a meaningful "
            "comparison.\n"
        )

    _seed_documents()

    for ticket in EVAL_TICKETS:
        print(f"\n{'=' * 70}\nTicket: {ticket.title}\n{ticket.description}\n{'=' * 70}")

        without_rag = _run_analysis(ticket, use_rag=False)
        _print_result("WITHOUT RAG", *without_rag)

        with_rag = _run_analysis(ticket, use_rag=True)
        _print_result("WITH RAG", *with_rag)


if __name__ == "__main__":
    main()
