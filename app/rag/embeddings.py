"""OpenAI embedding client wrapper for the RAG module.

Mirrors the singleton-client pattern in app/agent/llm.py::get_client(): one
lazily-instantiated, module-level client, reused everywhere via import.
"""

from openai import OpenAI

from app.core.config import settings

_client: OpenAI | None = None


def get_embedding_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


class EmbeddingError(RuntimeError):
    """Raised when OpenAI embedding generation fails or returns something unusable."""


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts with settings.embedding_model.

    Raises EmbeddingError (never a raw OpenAI/network exception) on API
    failure, and ValueError if `texts` is empty - embedding nothing is a
    caller bug, not an external-service failure.
    """
    if not texts:
        raise ValueError("texts must not be empty")

    client = get_embedding_client()

    try:
        response = client.embeddings.create(model=settings.embedding_model, input=texts)
    except Exception as exc:
        raise EmbeddingError(f"OpenAI embedding call failed: {exc}") from exc

    embeddings = [item.embedding for item in response.data]
    if len(embeddings) != len(texts):
        raise EmbeddingError(
            f"OpenAI returned {len(embeddings)} embedding(s) for {len(texts)} input text(s)."
        )

    return embeddings


def embed_text(text: str) -> list[float]:
    """Embed a single text. Convenience wrapper around embed_texts."""
    return embed_texts([text])[0]
