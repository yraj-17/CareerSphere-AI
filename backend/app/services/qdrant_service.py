"""
Qdrant vector-store service.

PostgreSQL keeps structured metadata; Qdrant stores embeddings and
vector-search payloads for profile similarity, career matching, and
content recommendations.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import settings

_client: Optional[QdrantClient] = None


def get_qdrant_client() -> QdrantClient:
    global _client
    if _client is None:
        kwargs: Dict[str, Any] = {
            "url": settings.QDRANT_URL,
            "prefer_grpc": False,
            "check_compatibility": False,
        }
        if settings.QDRANT_API_KEY:
            kwargs["api_key"] = settings.QDRANT_API_KEY
        _client = QdrantClient(**kwargs)
    return _client


def ping_qdrant() -> bool:
    try:
        get_qdrant_client().get_collections()
        return True
    except Exception:
        return False


def _vector_params() -> qmodels.VectorParams:
    return qmodels.VectorParams(
        size=settings.EMBEDDING_DIMENSION,
        distance=qmodels.Distance.COSINE,
    )


def ensure_collection(collection_name: str) -> None:
    """Create a collection if it does not already exist."""
    client = get_qdrant_client()
    existing = {c.name for c in client.get_collections().collections}
    if collection_name in existing:
        return
    client.create_collection(
        collection_name=collection_name,
        vectors_config=_vector_params(),
    )
    print(f"[Qdrant] Created collection '{collection_name}'.")


def ensure_default_collections() -> None:
    """Ensure profile + content collections exist for AI matching features."""
    ensure_collection(settings.QDRANT_COLLECTION_PROFILES)
    ensure_collection(settings.QDRANT_COLLECTION_CONTENT)
    print("[Qdrant] Default collections ready.")


def upsert_embedding(
    collection_name: str,
    point_id: str,
    vector: Sequence[float],
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    if len(vector) != settings.EMBEDDING_DIMENSION:
        raise ValueError(
            f"Expected embedding dimension {settings.EMBEDDING_DIMENSION}, got {len(vector)}"
        )
    get_qdrant_client().upsert(
        collection_name=collection_name,
        points=[
            qmodels.PointStruct(
                id=point_id,
                vector=list(vector),
                payload=payload or {},
            )
        ],
    )


def similarity_search(
    collection_name: str,
    query_vector: Sequence[float],
    limit: int = 10,
    score_threshold: Optional[float] = None,
    query_filter: Optional[qmodels.Filter] = None,
) -> List[qmodels.ScoredPoint]:
    if len(query_vector) != settings.EMBEDDING_DIMENSION:
        raise ValueError(
            f"Expected embedding dimension {settings.EMBEDDING_DIMENSION}, got {len(query_vector)}"
        )
    client = get_qdrant_client()
    # Prefer query_points (qdrant-client >= 1.14); fall back to search for older clients
    if hasattr(client, "query_points"):
        result = client.query_points(
            collection_name=collection_name,
            query=list(query_vector),
            limit=limit,
            score_threshold=score_threshold,
            query_filter=query_filter,
        )
        return list(result.points)
    return client.search(
        collection_name=collection_name,
        query_vector=list(query_vector),
        limit=limit,
        score_threshold=score_threshold,
        query_filter=query_filter,
    )


def delete_vectors(collection_name: str, point_ids: List[str]) -> None:
    if not point_ids:
        return
    get_qdrant_client().delete(
        collection_name=collection_name,
        points_selector=qmodels.PointIdsList(points=point_ids),
    )


def retrieve_points(collection_name: str, point_ids: List[str]) -> List[qmodels.Record]:
    if not point_ids:
        return []
    return get_qdrant_client().retrieve(
        collection_name=collection_name,
        ids=point_ids,
        with_payload=True,
        with_vectors=False,
    )
