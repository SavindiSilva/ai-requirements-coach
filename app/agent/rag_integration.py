"""Temporary Phase 3 evaluation glue between app/agent, app/coaching, and app/rag.

This module exists solely to let RAG retrieval be evaluated against the
analysis/coaching prompts before real project context (from Jira/the
frontend) exists. `TEMP_EVAL_PROJECT_ID` is a single, explicitly temporary
constant - see CLAUDE.md section 7 ("Temporary evaluation scope") for the
full rationale and the plan to replace it.

Do not extend this pattern: no other module should hardcode a project_id.
This file is the one place that does, and it exists only to be deleted (or
have the constant replaced by a real project_id) once one is available.

Retrieval failures must never break analysis or coaching (CLAUDE.md
section 25), so `get_retrieved_context()` fails safe: it returns []
(never raises) whenever OPENAI_API_KEY is not configured, or whenever the
underlying RAG call raises EmbeddingError, RAGStoreError, or ValueError.
"""

import logging

from app.core.config import settings
from app.rag.embeddings import EmbeddingError
from app.rag.schemas import RetrievedChunk
from app.rag.store import RAGStoreError, retrieve

logger = logging.getLogger(__name__)

TEMP_EVAL_PROJECT_ID = "default"


def get_retrieved_context(
    query_text: str,
    project_id: str = TEMP_EVAL_PROJECT_ID,
    k: int = 5,
) -> list[RetrievedChunk]:
    """Retrieve relevant project chunks for `query_text`, failing safe.

    Returns [] (never raises) if OPENAI_API_KEY is not configured, or if
    retrieval fails for any reason - analysis/coaching must still work with
    no RAG context available.
    """
    if not settings.openai_api_key:
        return []

    try:
        return retrieve(project_id=project_id, query_text=query_text, k=k)
    except (EmbeddingError, RAGStoreError, ValueError) as exc:
        logger.warning("RAG retrieval failed, continuing without context: %s", exc)
        return []


def format_context_for_prompt(chunks: list[RetrievedChunk]) -> str:
    """Format retrieved chunks into a prompt-ready block, or "" if there are none."""
    if not chunks:
        return ""

    formatted = "\n\n".join(
        f"[{chunk.metadata.document_type.value}] {chunk.metadata.title}:\n{chunk.text}"
        for chunk in chunks
    )
    return (
        "Relevant project context (from project documentation - supplementary "
        "background, not authoritative over the ticket text itself):\n\n"
        f"{formatted}"
    )
