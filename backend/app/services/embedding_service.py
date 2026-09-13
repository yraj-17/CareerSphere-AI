from __future__ import annotations

from functools import lru_cache
from typing import Any, Sequence

from ollama import Client
from httpx import TimeoutException

from app.core.config import settings


class EmbeddingServiceError(Exception):
    """Raised when text cannot be converted into an embedding vector."""


def _clean_text(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError("Text to embed cannot be empty.")
    return cleaned


def _extract_embeddings(response: Any) -> list[list[float]]:
    if isinstance(response, dict):
        embeddings = response.get("embeddings")
        if embeddings is None and response.get("embedding") is not None:
            embeddings = [response["embedding"]]
    else:
        embeddings = getattr(response, "embeddings", None)
        if embeddings is None and getattr(response, "embedding", None) is not None:
            embeddings = [getattr(response, "embedding")]

    if not isinstance(embeddings, Sequence) or not embeddings:
        raise EmbeddingServiceError("Embedding model returned an unexpected response.")

    vectors = [list(vector) for vector in embeddings]
    if any(not vector or not all(isinstance(value, (int, float)) for value in vector) for vector in vectors):
        raise EmbeddingServiceError("Embedding model returned an invalid vector.")
    return [[float(value) for value in vector] for vector in vectors]


def get_embedding_client() -> Client:
    if settings.EMBEDDING_PROVIDER != "ollama":
        raise EmbeddingServiceError(f"Unsupported embedding provider: {settings.EMBEDDING_PROVIDER}")
    return Client(host=settings.OLLAMA_BASE_URL, timeout=settings.OLLAMA_TIMEOUT_SECONDS)


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    cleaned = [_clean_text(text) for text in texts]
    if not cleaned:
        raise ValueError("At least one text is required.")

    try:
        response = get_embedding_client().embed(
            model=settings.EMBEDDING_MODEL,
            input=cleaned,
        )
    except TimeoutException as exc:
        raise EmbeddingServiceError("The embedding model is taking longer than expected. Please try again.") from exc
    except Exception as exc:
        raise EmbeddingServiceError("Embedding service is currently unavailable. Please try again later.") from exc

    vectors = _extract_embeddings(response)
    if len(vectors) != len(cleaned):
        raise EmbeddingServiceError("Embedding model returned the wrong number of vectors.")
    dimensions = {len(vector) for vector in vectors}
    if len(dimensions) != 1:
        raise EmbeddingServiceError("Embedding model returned inconsistent vector dimensions.")
    return vectors


@lru_cache(maxsize=1)
def get_embedding_dimension() -> int:
    if settings.EMBEDDING_DIMENSION:
        return settings.EMBEDDING_DIMENSION
    return len(embed_text("CareerSphere embedding dimension probe"))
