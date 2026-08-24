"""Pydantic schemas for the standalone Phase 3 RAG module.

`DocumentInput` is what a caller supplies to ingest a document.
`ChunkMetadata` is the metadata stored on every ChromaDB chunk record.
`RetrievedChunk` is the structured shape returned by retrieval - callers
never see raw ChromaDB dicts.
"""

from enum import Enum

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    GENERAL = "general"
    DEFINITION_OF_READY = "definition_of_ready"
    ENGINEERING_GUIDELINE = "engineering_guideline"
    SECURITY_GUIDELINE = "security_guideline"
    PRODUCT_RULE = "product_rule"
    ARCHITECTURE_GUIDELINE = "architecture_guideline"
    PROJECT_REQUIREMENT = "project_requirement"


class DocumentInput(BaseModel):
    project_id: str = Field(..., min_length=1)
    document_type: DocumentType = Field(
        default=DocumentType.GENERAL,
        description="Optional. Defaults to GENERAL when the caller doesn't categorize the upload.",
    )
    title: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)


class ChunkMetadata(BaseModel):
    project_id: str
    document_id: str
    document_type: DocumentType
    title: str
    chunk_index: int = Field(..., ge=0)


class IngestResult(BaseModel):
    document_id: str
    chunk_count: int = Field(..., ge=0)


class RetrievedChunk(BaseModel):
    text: str
    metadata: ChunkMetadata
    distance: float = Field(..., description="Vector distance from the query (lower is more relevant).")


class DocumentSummary(BaseModel):
    """One entry per distinct uploaded document (not one per chunk).

    Returned by GET /api/knowledge/documents so a project's Knowledge panel
    can show what's already stored without keeping its own local list.
    """

    document_id: str
    title: str
    document_type: DocumentType
