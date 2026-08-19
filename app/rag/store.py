"""ChromaDB-backed ingestion and retrieval for the standalone Phase 3 RAG module.

This is the module's ingestion/retrieval service: it combines chunking
(app/rag/chunking.py) and embedding (app/rag/embeddings.py) with a
persistent ChromaDB collection. There is no separate API router yet and
this is not wired into the analysis/coaching prompts - see CLAUDE.md
section 20 and docs/architecture.md for why.

Every chunk is stored with project_id metadata, and retrieval always
filters by project_id, so a query for one project can never return another
project's chunks.
"""

import uuid

import chromadb

from app.core.config import settings
from app.rag.chunking import chunk_text
from app.rag.embeddings import embed_text, embed_texts
from app.rag.schemas import ChunkMetadata, DocumentInput, DocumentType, IngestResult, RetrievedChunk

COLLECTION_NAME = "project_documents"
DEFAULT_TOP_K = 5

_client: chromadb.ClientAPI | None = None


class RAGStoreError(RuntimeError):
    """Raised when a ChromaDB read/write operation fails."""


def get_chroma_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    return _client


def get_collection():
    return get_chroma_client().get_or_create_collection(COLLECTION_NAME)


def add_document(document: DocumentInput, document_id: str | None = None) -> IngestResult:
    """Chunk, embed, and store a document under its project_id.

    Raises ValueError if the document text produces no chunks (e.g. it is
    whitespace-only despite passing schema validation is not possible here,
    since DocumentInput.text already requires min_length=1, but this stays
    defensive for callers constructing chunks directly). Raises
    EmbeddingError if embedding fails, or RAGStoreError if the ChromaDB
    write fails.
    """
    document_id = document_id or str(uuid.uuid4())

    chunks = chunk_text(document.text)
    if not chunks:
        raise ValueError("document text must not be empty")

    embeddings = embed_texts(chunks)

    ids = [f"{document_id}-{i}" for i in range(len(chunks))]
    metadatas = [
        ChunkMetadata(
            project_id=document.project_id,
            document_id=document_id,
            document_type=document.document_type,
            title=document.title,
            chunk_index=i,
        ).model_dump(mode="json")
        for i in range(len(chunks))
    ]

    try:
        get_collection().add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
    except Exception as exc:
        raise RAGStoreError(f"Failed to store document chunks in ChromaDB: {exc}") from exc

    return IngestResult(document_id=document_id, chunk_count=len(chunks))


def retrieve(
    project_id: str,
    query_text: str,
    k: int = DEFAULT_TOP_K,
    document_type: DocumentType | None = None,
) -> list[RetrievedChunk]:
    """Retrieve the top-k most relevant chunks for `query_text`, scoped to `project_id`.

    project_id is required and always applied as a metadata filter, so
    chunks belonging to another project are never returned - this is
    enforced here, not left to the caller. Raises ValueError for invalid
    input, EmbeddingError if embedding the query fails, or RAGStoreError if
    the ChromaDB query fails.
    """
    if not project_id or not project_id.strip():
        raise ValueError("project_id is required for retrieval")
    if not query_text or not query_text.strip():
        raise ValueError("query_text must not be empty")
    if k <= 0:
        raise ValueError("k must be positive")

    query_embedding = embed_text(query_text)

    where = {"project_id": project_id}
    if document_type is not None:
        where = {"$and": [{"project_id": project_id}, {"document_type": document_type.value}]}

    try:
        results = get_collection().query(query_embeddings=[query_embedding], n_results=k, where=where)
    except Exception as exc:
        raise RAGStoreError(f"Failed to query ChromaDB: {exc}") from exc

    documents = (results.get("documents") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]
    distances = (results.get("distances") or [[]])[0]

    return [
        RetrievedChunk(text=text, metadata=ChunkMetadata.model_validate(metadata), distance=distance)
        for text, metadata, distance in zip(documents, metadatas, distances)
    ]
