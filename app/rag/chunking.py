"""Pure text chunking for the RAG ingestion pipeline.

Word-based, deterministic, and side-effect free by design so it can be unit
tested directly with no embedding or ChromaDB calls - mirrors the
"pure and LLM-free by design" convention already used for
app/coaching/selection.py and app/coaching/stop_condition.py.
"""

DEFAULT_CHUNK_SIZE = 200
DEFAULT_CHUNK_OVERLAP = 20


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split `text` into overlapping chunks of up to `chunk_size` words.

    Returns [] for blank/whitespace-only input. A document with `chunk_size`
    words or fewer is returned as a single chunk (stripped, otherwise
    unmodified) rather than being split unnecessarily.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and less than chunk_size")

    words = text.split()
    if not words:
        return []

    if len(words) <= chunk_size:
        return [text.strip()]

    chunks: list[str] = []
    step = chunk_size - chunk_overlap
    for start in range(0, len(words), step):
        chunk_words = words[start : start + chunk_size]
        if not chunk_words:
            break
        chunks.append(" ".join(chunk_words))
        if start + chunk_size >= len(words):
            break

    return chunks
