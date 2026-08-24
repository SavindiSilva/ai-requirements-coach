"""Tests for the standalone Phase 3 RAG module (app/rag/).

Chunking and input-validation tests are pure/deterministic and always run.

Tests that need a real embedding (ingest/retrieve end-to-end, cross-project
filtering, metadata preservation) are skipped when OPENAI_API_KEY is not
configured locally, mirroring how tests/test_analysis.py and
tests/test_coaching.py depend on a locally-configured ANTHROPIC_API_KEY -
this is a missing local credential, not a code issue.

Each embedding-requiring test uses a fresh uuid4 project_id, so tests stay
isolated and repeatable even though ChromaDB storage is persistent across
runs (chroma_data/) - the same project_id-filtering behaviour under test is
what keeps each run from seeing another run's chunks.

The typed-embedding-error test deliberately swaps in a client configured
with an invalid API key and makes a real call against it (no response
mocking) - this exercises the real failure path regardless of whether a
valid OPENAI_API_KEY happens to be configured locally.
"""

import uuid

import pytest
from openai import OpenAI
from pydantic import ValidationError

from app.core.config import settings
from app.rag import embeddings as embeddings_module
from app.rag.chunking import chunk_text
from app.rag.embeddings import EmbeddingError, embed_texts
from app.rag.schemas import DocumentInput, DocumentType
from app.rag.store import RAGStoreError, add_document, get_collection, list_documents, retrieve

requires_openai = pytest.mark.skipif(
    not settings.openai_api_key,
    reason="OPENAI_API_KEY not configured locally - skipping real-embedding RAG tests",
)


# --- chunking (pure, always runs) ---------------------------------------


def test_chunk_text_splits_long_text_into_multiple_overlapping_chunks():
    text = " ".join(f"word{i}" for i in range(450))
    chunks = chunk_text(text, chunk_size=200, chunk_overlap=20)

    assert len(chunks) == 3
    assert chunks[0].split()[0] == "word0"
    assert chunks[0].split()[-1] == "word199"
    # step = chunk_size - chunk_overlap = 180, so chunk 2 starts at word180
    assert chunks[1].split()[0] == "word180"
    assert chunks[2].split()[-1] == "word449"


def test_chunk_text_short_document_remains_a_single_intact_chunk():
    text = " ".join(f"w{i}" for i in range(50))
    chunks = chunk_text(text, chunk_size=200, chunk_overlap=20)

    assert chunks == [text]


def test_chunk_text_empty_or_whitespace_input_returns_empty_list():
    assert chunk_text("") == []
    assert chunk_text("   \n\t  ") == []


def test_chunk_text_invalid_chunk_size_raises_value_error():
    with pytest.raises(ValueError):
        chunk_text("some text", chunk_size=0)

    with pytest.raises(ValueError):
        chunk_text("some text", chunk_size=10, chunk_overlap=10)

    with pytest.raises(ValueError):
        chunk_text("some text", chunk_size=10, chunk_overlap=-1)


# --- input validation (pure, always runs) -------------------------------


def test_document_input_defaults_document_type_to_general_when_omitted():
    document = DocumentInput(project_id="proj-1", title="Untyped", text="Some notes.")
    assert document.document_type == DocumentType.GENERAL


def test_list_documents_requires_non_blank_project_id():
    with pytest.raises(ValueError):
        list_documents("")

    with pytest.raises(ValueError):
        list_documents("   ")


def test_document_input_rejects_empty_text():
    with pytest.raises(ValidationError):
        DocumentInput(
            project_id="proj-1",
            document_type=DocumentType.PRODUCT_RULE,
            title="Empty",
            text="",
        )


def test_add_document_whitespace_only_text_raises_value_error():
    document = DocumentInput(
        project_id="proj-1",
        document_type=DocumentType.PRODUCT_RULE,
        title="Whitespace only",
        text="   ",
    )
    with pytest.raises(ValueError):
        add_document(document)


def test_retrieve_requires_non_blank_project_id():
    with pytest.raises(ValueError):
        retrieve(project_id="", query_text="anything")

    with pytest.raises(ValueError):
        retrieve(project_id="   ", query_text="anything")


def test_retrieve_requires_non_blank_query_text():
    with pytest.raises(ValueError):
        retrieve(project_id="proj-1", query_text="")


def test_embed_texts_empty_list_raises_value_error():
    with pytest.raises(ValueError):
        embed_texts([])


# --- embedding failure (real API call, invalid key, always runs) -------


def test_embed_texts_raises_embedding_error_on_invalid_api_key(monkeypatch):
    monkeypatch.setattr(embeddings_module, "_client", OpenAI(api_key="sk-invalid-test-key-000"))

    with pytest.raises(EmbeddingError):
        embed_texts(["this call should fail authentication"])


# --- ingestion + retrieval end-to-end (real embeddings required) -------


@requires_openai
def test_add_document_stores_chunks_in_chromadb():
    project_id = f"test-{uuid.uuid4()}"
    document = DocumentInput(
        project_id=project_id,
        document_type=DocumentType.DEFINITION_OF_READY,
        title="Definition of Ready",
        text=(
            "A ticket is ready for development when it has clear acceptance "
            "criteria, a defined scope, and no unresolved open questions."
        ),
    )

    result = add_document(document)

    assert result.chunk_count >= 1

    stored = get_collection().get(where={"document_id": result.document_id})
    assert len(stored["ids"]) == result.chunk_count
    for metadata in stored["metadatas"]:
        assert metadata["project_id"] == project_id
        assert metadata["document_id"] == result.document_id
        assert metadata["document_type"] == DocumentType.DEFINITION_OF_READY.value
        assert metadata["title"] == "Definition of Ready"


@requires_openai
def test_retrieve_returns_relevant_chunks():
    project_id = f"test-{uuid.uuid4()}"
    document = DocumentInput(
        project_id=project_id,
        document_type=DocumentType.SECURITY_GUIDELINE,
        title="Refund Policy",
        text="Refunds over $500 require manager approval before being processed.",
    )
    add_document(document)

    results = retrieve(project_id=project_id, query_text="What approval is needed for large refunds?", k=3)

    assert len(results) >= 1
    assert any("refund" in chunk.text.lower() for chunk in results)


@requires_openai
def test_retrieve_project_id_filtering_prevents_cross_project_retrieval():
    project_a = f"test-{uuid.uuid4()}"
    project_b = f"test-{uuid.uuid4()}"

    add_document(
        DocumentInput(
            project_id=project_a,
            document_type=DocumentType.ARCHITECTURE_GUIDELINE,
            title="Project A secret architecture note",
            text="Project Alpha uses a bespoke quantum-flux caching layer codenamed Zylorath.",
        )
    )
    add_document(
        DocumentInput(
            project_id=project_b,
            document_type=DocumentType.ARCHITECTURE_GUIDELINE,
            title="Project B architecture note",
            text="Project Beta uses a standard Redis cache with a five minute TTL.",
        )
    )

    results = retrieve(project_id=project_b, query_text="quantum-flux caching layer Zylorath", k=5)

    assert all(chunk.metadata.project_id == project_b for chunk in results)
    assert not any("Zylorath" in chunk.text for chunk in results)


@requires_openai
def test_retrieve_metadata_is_preserved():
    project_id = f"test-{uuid.uuid4()}"
    document = DocumentInput(
        project_id=project_id,
        document_type=DocumentType.ENGINEERING_GUIDELINE,
        title="Coding Standards",
        text="All new endpoints must declare an explicit response_model.",
    )
    result = add_document(document)

    results = retrieve(project_id=project_id, query_text="response_model requirement", k=5)

    assert len(results) >= 1
    chunk = results[0]
    assert chunk.metadata.project_id == project_id
    assert chunk.metadata.document_id == result.document_id
    assert chunk.metadata.document_type == DocumentType.ENGINEERING_GUIDELINE
    assert chunk.metadata.title == "Coding Standards"
    assert chunk.metadata.chunk_index == 0


@requires_openai
def test_list_documents_returns_one_entry_per_document_not_per_chunk():
    project_id = f"test-{uuid.uuid4()}"
    long_text = " ".join(f"word{i}" for i in range(450))  # chunks into 3 pieces
    result = add_document(
        DocumentInput(
            project_id=project_id,
            document_type=DocumentType.ENGINEERING_GUIDELINE,
            title="Multi-chunk Guideline",
            text=long_text,
        )
    )
    assert result.chunk_count > 1  # sanity check the fixture actually spans multiple chunks

    documents = list_documents(project_id)

    assert len(documents) == 1
    assert documents[0].document_id == result.document_id
    assert documents[0].title == "Multi-chunk Guideline"
    assert documents[0].document_type == DocumentType.ENGINEERING_GUIDELINE


@requires_openai
def test_list_documents_only_includes_the_requested_project():
    project_a = f"test-{uuid.uuid4()}"
    project_b = f"test-{uuid.uuid4()}"

    add_document(
        DocumentInput(project_id=project_a, title="Project A doc", text="Project A guideline text.")
    )
    add_document(
        DocumentInput(project_id=project_b, title="Project B doc", text="Project B guideline text.")
    )

    documents = list_documents(project_b)

    assert [doc.title for doc in documents] == ["Project B doc"]


@requires_openai
def test_add_document_generates_document_id_when_not_supplied():
    project_id = f"test-{uuid.uuid4()}"
    document = DocumentInput(
        project_id=project_id,
        document_type=DocumentType.PRODUCT_RULE,
        title="Auto ID",
        text="Every user must verify their email before creating a project.",
    )

    result = add_document(document)

    assert result.document_id
    uuid.UUID(result.document_id)  # does not raise
