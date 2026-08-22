"""Tests for company/project knowledge document upload.

Covers app/rag/extraction.py (pure text extraction) and app/rag/router.py
(the POST /api/knowledge/upload endpoint).

Extraction tests call extract_text() directly with no FastAPI, network, or
ChromaDB involvement - they exercise txt/md/docx round-trips for real, and
mock only pypdf.PdfReader for the PDF case (constructing a real
text-bearing PDF byte-for-byte isn't worth the complexity here; pypdf's own
parsing is out of scope for this project's tests, only our wrapper around
it is).

Endpoint tests use FastAPI's TestClient against the real app (same
convention as tests/test_jira.py) and monkeypatch app.rag.router.add_document
so no OpenAI embedding call or real ChromaDB write happens - the existing
add_document()/ChromaDB pipeline is already covered by tests/test_rag.py
and is not re-tested here.
"""

from io import BytesIO

import pytest
from docx import Document as DocxDocument
from fastapi.testclient import TestClient

from app.main import app
from app.rag import extraction
from app.rag.embeddings import EmbeddingError
from app.rag.extraction import ExtractionError, UnsupportedFileTypeError, extract_text
from app.rag.schemas import DocumentInput, DocumentType, IngestResult
from app.rag.store import RAGStoreError

client_app = TestClient(app)


def _make_docx_bytes(paragraphs: list[str]) -> bytes:
    document = DocxDocument()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


class _FakePdfPage:
    def __init__(self, text: str):
        self._text = text

    def extract_text(self) -> str:
        return self._text


class _FakePdfReader:
    def __init__(self, stream):
        self.pages = [_FakePdfPage("First page text."), _FakePdfPage("Second page text.")]


class _FailingPdfReader:
    def __init__(self, stream):
        raise ValueError("not a real PDF")


# --- app/rag/extraction.py: extract_text (pure, no network/ChromaDB) --------


def test_extract_text_txt_decodes_utf8():
    text = extract_text("notes.txt", "Some plain notes about the widget flow.".encode("utf-8"))
    assert text == "Some plain notes about the widget flow."


def test_extract_text_md_decodes_utf8():
    text = extract_text("notes.md", "# Heading\n\nSome markdown notes.".encode("utf-8"))
    assert "# Heading" in text
    assert "Some markdown notes." in text


def test_extract_text_pdf_extracts_page_text(monkeypatch):
    monkeypatch.setattr(extraction, "PdfReader", _FakePdfReader)

    text = extract_text("policy.pdf", b"fake-pdf-bytes")

    assert "First page text." in text
    assert "Second page text." in text


def test_extract_text_pdf_extraction_failure_raises_extraction_error(monkeypatch):
    monkeypatch.setattr(extraction, "PdfReader", _FailingPdfReader)

    with pytest.raises(ExtractionError):
        extract_text("policy.pdf", b"not-really-a-pdf")


def test_extract_text_docx_extracts_paragraph_text():
    content = _make_docx_bytes(["First paragraph.", "Second paragraph."])

    text = extract_text("guidelines.docx", content)

    assert "First paragraph." in text
    assert "Second paragraph." in text


def test_extract_text_unsupported_extension_raises():
    with pytest.raises(UnsupportedFileTypeError):
        extract_text("diagram.png", b"\x89PNG\r\n")


def test_extract_text_whitespace_only_content_raises_extraction_error():
    with pytest.raises(ExtractionError):
        extract_text("empty.txt", b"   \n\t  ")


# --- POST /api/knowledge/upload ----------------------------------------------


def _txt_file(name: str = "notes.txt", body: bytes = b"Refunds require manager approval."):
    return {"file": (name, body, "text/plain")}


def test_upload_txt_succeeds_and_forwards_expected_document(monkeypatch):
    captured: dict = {}

    def _fake_add_document(document: DocumentInput, document_id=None) -> IngestResult:
        captured["document"] = document
        return IngestResult(document_id="doc-1", chunk_count=1)

    monkeypatch.setattr("app.rag.router.add_document", _fake_add_document)

    response = client_app.post(
        "/api/knowledge/upload",
        files=_txt_file(),
        data={"project_id": "proj-1", "document_type": "product_rule", "title": "Refund Policy"},
    )

    assert response.status_code == 200
    assert response.json() == {"document_id": "doc-1", "chunk_count": 1}

    document = captured["document"]
    assert document.project_id == "proj-1"
    assert document.document_type == DocumentType.PRODUCT_RULE
    assert document.title == "Refund Policy"
    assert document.text == "Refunds require manager approval."


def test_upload_md_succeeds(monkeypatch):
    monkeypatch.setattr(
        "app.rag.router.add_document",
        lambda document, document_id=None: IngestResult(document_id="doc-2", chunk_count=1),
    )

    response = client_app.post(
        "/api/knowledge/upload",
        files={"file": ("dor.md", b"# Definition of Ready\n\nMust have acceptance criteria.", "text/markdown")},
        data={"project_id": "proj-1", "document_type": "definition_of_ready"},
    )

    assert response.status_code == 200
    assert response.json() == {"document_id": "doc-2", "chunk_count": 1}


def test_upload_title_defaults_to_filename_when_omitted(monkeypatch):
    captured: dict = {}

    def _fake_add_document(document: DocumentInput, document_id=None) -> IngestResult:
        captured["document"] = document
        return IngestResult(document_id="doc-3", chunk_count=1)

    monkeypatch.setattr("app.rag.router.add_document", _fake_add_document)

    response = client_app.post(
        "/api/knowledge/upload",
        files=_txt_file(name="security-guidelines.txt"),
        data={"project_id": "proj-1", "document_type": "security_guideline"},
    )

    assert response.status_code == 200
    assert captured["document"].title == "security-guidelines.txt"


def test_upload_unsupported_extension_returns_400(monkeypatch):
    def _fail_if_called(document, document_id=None):
        raise AssertionError("add_document must not be called for an unsupported file type")

    monkeypatch.setattr("app.rag.router.add_document", _fail_if_called)

    response = client_app.post(
        "/api/knowledge/upload",
        files={"file": ("diagram.png", b"\x89PNG\r\n", "image/png")},
        data={"project_id": "proj-1", "document_type": "product_rule"},
    )

    assert response.status_code == 400


def test_upload_empty_extracted_document_returns_400(monkeypatch):
    def _fail_if_called(document, document_id=None):
        raise AssertionError("add_document must not be called for an empty document")

    monkeypatch.setattr("app.rag.router.add_document", _fail_if_called)

    response = client_app.post(
        "/api/knowledge/upload",
        files=_txt_file(body=b"   \n  "),
        data={"project_id": "proj-1", "document_type": "product_rule"},
    )

    assert response.status_code == 400


def test_upload_missing_project_id_returns_422(monkeypatch):
    def _fail_if_called(document, document_id=None):
        raise AssertionError("add_document must not be called when project_id is missing")

    monkeypatch.setattr("app.rag.router.add_document", _fail_if_called)

    response = client_app.post(
        "/api/knowledge/upload",
        files=_txt_file(),
        data={"document_type": "product_rule"},
    )

    assert response.status_code == 422


def test_upload_file_larger_than_10mb_returns_413(monkeypatch):
    def _fail_if_called(document, document_id=None):
        raise AssertionError("add_document must not be called for an oversized file")

    monkeypatch.setattr("app.rag.router.add_document", _fail_if_called)

    oversized_body = b"x" * (10 * 1024 * 1024 + 1)
    response = client_app.post(
        "/api/knowledge/upload",
        files=_txt_file(body=oversized_body),
        data={"project_id": "proj-1", "document_type": "product_rule"},
    )

    assert response.status_code == 413


def test_upload_embedding_error_returns_502(monkeypatch):
    def _raise(document, document_id=None):
        raise EmbeddingError("OpenAI embedding call failed")

    monkeypatch.setattr("app.rag.router.add_document", _raise)

    response = client_app.post(
        "/api/knowledge/upload",
        files=_txt_file(),
        data={"project_id": "proj-1", "document_type": "product_rule"},
    )

    assert response.status_code == 502


def test_upload_rag_store_error_returns_502(monkeypatch):
    def _raise(document, document_id=None):
        raise RAGStoreError("Failed to store document chunks in ChromaDB")

    monkeypatch.setattr("app.rag.router.add_document", _raise)

    response = client_app.post(
        "/api/knowledge/upload",
        files=_txt_file(),
        data={"project_id": "proj-1", "document_type": "product_rule"},
    )

    assert response.status_code == 502


def test_upload_returns_ingest_result_from_add_document(monkeypatch):
    monkeypatch.setattr(
        "app.rag.router.add_document",
        lambda document, document_id=None: IngestResult(document_id="doc-xyz", chunk_count=4),
    )

    response = client_app.post(
        "/api/knowledge/upload",
        files=_txt_file(),
        data={"project_id": "proj-1", "document_type": "product_rule"},
    )

    assert response.status_code == 200
    assert response.json() == {"document_id": "doc-xyz", "chunk_count": 4}
