"""Text extraction for uploaded company/project knowledge documents.

Pure functions: given a filename and raw bytes, return extracted text. No
FastAPI, ChromaDB, or embedding dependency here, so this stays independently
unit-testable - mirrors the "pure and LLM-free by design" convention already
used for app/rag/chunking.py.

This module only extracts text. Chunking, embedding, and storage remain the
sole responsibility of app/rag/chunking.py and app/rag/store.py::add_document
- this module does not duplicate or bypass that pipeline.
"""

from io import BytesIO

from docx import Document
from pypdf import PdfReader

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}


class UnsupportedFileTypeError(ValueError):
    """Raised when a filename's extension is not one of SUPPORTED_EXTENSIONS."""


class ExtractionError(RuntimeError):
    """Raised when extraction fails, or yields no non-whitespace text.

    An empty/whitespace-only result is treated as an error here rather than
    left to the caller, so an empty document can never be silently forwarded
    to add_document().
    """


def _extension(filename: str) -> str:
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def _extract_txt_or_md(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExtractionError(f"Failed to decode text file as UTF-8: {exc}") from exc


def _extract_pdf(content: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise ExtractionError(f"Failed to extract text from PDF: {exc}") from exc
    return "\n\n".join(pages)


def _extract_docx(content: bytes) -> str:
    try:
        document = Document(BytesIO(content))
        paragraphs = [p.text for p in document.paragraphs]
    except Exception as exc:
        raise ExtractionError(f"Failed to extract text from DOCX: {exc}") from exc
    return "\n".join(paragraphs)


def extract_text(filename: str, content: bytes) -> str:
    """Extract plain text from an uploaded document's raw bytes.

    Raises UnsupportedFileTypeError if `filename`'s extension is not in
    SUPPORTED_EXTENSIONS, or ExtractionError if extraction fails or the
    result has no non-whitespace text.
    """
    extension = _extension(filename)
    if extension not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{extension or filename}'. "
            f"Supported extensions: {', '.join(sorted(SUPPORTED_EXTENSIONS))}."
        )

    if extension in (".txt", ".md"):
        text = _extract_txt_or_md(content)
    elif extension == ".pdf":
        text = _extract_pdf(content)
    else:  # .docx
        text = _extract_docx(content)

    if not text.strip():
        raise ExtractionError("Extracted document text is empty.")

    return text
