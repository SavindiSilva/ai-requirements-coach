"""FastAPI router for company/project knowledge document upload.

Additive slice on top of the existing standalone RAG module: accepts an
uploaded file, extracts its text (app/rag/extraction.py), and ingests it
through the EXISTING app.rag.store.add_document() - the same
chunk/embed/store pipeline already covered by tests/test_rag.py. This
router introduces no second ingestion path; it is a thin HTTP adapter in
front of add_document().

Mounted at /api/knowledge in app/main.py: POST /api/knowledge/upload
ingests a document, GET /api/knowledge/documents lists what's already
stored for a project (one entry per document, not per chunk) so the
frontend's Knowledge panel can show existing uploads instead of starting
from an empty local list.

No auth: the application has no auth system yet (app/auth/ is an empty
stub) - consistent with every other router in this codebase (see
app/jira/router.py, app/analysis/router.py, app/coaching/router.py).

project_id is accepted as an explicit required form field, not defaulted
to app/agent/rag_integration.py's TEMP_EVAL_PROJECT_ID - CLAUDE.md section 7
is explicit that the "default" hardcode must not be extended to new
features.

document_type is optional on upload (defaults to DocumentType.GENERAL) -
the frontend no longer asks the user to categorize a document before
uploading it; the field itself is untouched in storage/metadata.
"""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from app.rag.embeddings import EmbeddingError
from app.rag.extraction import ExtractionError, UnsupportedFileTypeError, extract_text
from app.rag.schemas import DocumentInput, DocumentSummary, DocumentType, IngestResult
from app.rag.store import RAGStoreError, add_document, list_documents

router = APIRouter()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/upload", response_model=IngestResult)
async def upload_knowledge_document(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    document_type: DocumentType = Form(DocumentType.GENERAL),
    title: str | None = Form(None),
) -> IngestResult:
    content = await file.read()

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the maximum upload size of {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    try:
        text = extract_text(file.filename or "", content)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        document = DocumentInput(
            project_id=project_id,
            document_type=document_type,
            title=(title or "").strip() or file.filename or "Untitled document",
            text=text,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        return add_document(document)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EmbeddingError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RAGStoreError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/documents", response_model=list[DocumentSummary])
def get_knowledge_documents(project_id: str) -> list[DocumentSummary]:
    try:
        return list_documents(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RAGStoreError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
