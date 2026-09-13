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
from app.services.embedding_service import embed_text, get_embedding_dimension

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


def get_vector_size() -> int:
    return get_embedding_dimension()


def _vector_params(vector_size: Optional[int] = None) -> qmodels.VectorParams:
    return qmodels.VectorParams(
        size=vector_size or get_vector_size(),
        distance=qmodels.Distance.COSINE,
    )


def collection_exists(collection_name: str) -> bool:
    client = get_qdrant_client()
    return client.collection_exists(collection_name=collection_name)


def ensure_collection(collection_name: str, vector_size: Optional[int] = None) -> None:
    """Create a collection if it does not already exist."""
    client = get_qdrant_client()
    if collection_exists(collection_name):
        return
    client.create_collection(
        collection_name=collection_name,
        vectors_config=_vector_params(vector_size=vector_size),
    )
    print(f"[Qdrant] Created collection '{collection_name}'.")


def ensure_default_collections() -> None:
    """Ensure profile + content collections exist for AI matching features."""
    vector_size = get_vector_size()
    ensure_collection(settings.QDRANT_COLLECTION_PROFILES, vector_size=vector_size)
    ensure_collection(settings.QDRANT_COLLECTION_CONTENT, vector_size=vector_size)
    print("[Qdrant] Default collections ready.")


def _validate_vector(vector: Sequence[float], vector_size: Optional[int] = None) -> list[float]:
    expected = vector_size or get_vector_size()
    values = [float(item) for item in vector]
    if len(values) != expected:
        raise ValueError(f"Expected embedding dimension {expected}, got {len(values)}")
    return values


def upsert_embedding(
    collection_name: str,
    point_id: str,
    vector: Sequence[float],
    payload: Optional[Dict[str, Any]] = None,
    vector_size: Optional[int] = None,
) -> None:
    upsert_vectors(
        collection_name=collection_name,
        points=[
            {
                "id": point_id,
                "vector": vector,
                "payload": payload or {},
            }
        ],
        vector_size=vector_size,
    )


def upsert_vectors(
    collection_name: str,
    points: Sequence[Dict[str, Any]],
    vector_size: Optional[int] = None,
) -> None:
    if not points:
        return
    structs = [
        qmodels.PointStruct(
            id=point["id"],
            vector=_validate_vector(point["vector"], vector_size=vector_size),
            payload=point.get("payload") or {},
        )
        for point in points
    ]
    get_qdrant_client().upsert(
        collection_name=collection_name,
        points=structs,
    )


def similarity_search(
    collection_name: str,
    query_vector: Sequence[float],
    limit: int = 10,
    score_threshold: Optional[float] = None,
    query_filter: Optional[qmodels.Filter] = None,
    vector_size: Optional[int] = None,
) -> List[qmodels.ScoredPoint]:
    vector = _validate_vector(query_vector, vector_size=vector_size)
    client = get_qdrant_client()
    # Prefer query_points (qdrant-client >= 1.14); fall back to search for older clients
    if hasattr(client, "query_points"):
        result = client.query_points(
            collection_name=collection_name,
            query=vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=query_filter,
        )
        return list(result.points)
    return client.search(
        collection_name=collection_name,
        query_vector=vector,
        limit=limit,
        score_threshold=score_threshold,
        query_filter=query_filter,
    )


def semantic_search(
    collection_name: str,
    query_text: str,
    limit: int = 10,
    score_threshold: Optional[float] = None,
    query_filter: Optional[qmodels.Filter] = None,
) -> List[qmodels.ScoredPoint]:
    query_vector = embed_text(query_text)
    return similarity_search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=limit,
        score_threshold=score_threshold,
        query_filter=query_filter,
        vector_size=len(query_vector),
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


def payload_for_text(source_type: str, source_id: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "source_type": source_type,
        "source_id": source_id,
        "text": text,
        "metadata": metadata or {},
    }
