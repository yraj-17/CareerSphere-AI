"""
Opportunity embedding and semantic retrieval service.

PostgreSQL remains the source of truth for opportunity records. This module
builds semantic documents from Opportunity rows, embeds one vector per
opportunity, and upserts those vectors into the dedicated Qdrant
``career_opportunities`` collection.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Sequence

from qdrant_client.http import models as qmodels
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.db.models import Opportunity
from app.services.embedding_service import embed_texts, get_embedding_dimension
from app.services.qdrant_service import (
    delete_vectors,
    ensure_collection,
    get_qdrant_client,
    semantic_search,
    upsert_vectors,
)

logger = logging.getLogger(__name__)

EXPECTED_EMBEDDING_DIMENSION = 768
_UUID_NAMESPACE = uuid.UUID("12345678-90ab-cdef-1234-567890abcdef")


class OpportunityEmbeddingError(Exception):
    """Raised when opportunity document/indexing validation fails."""


@dataclass(frozen=True)
class OpportunityDocument:
    opportunity_id: str
    point_id: str
    text: str
    payload: Dict[str, Any]


@dataclass(frozen=True)
class OpportunityIndexingResult:
    collection: str
    opportunities_found: int
    embeddings_generated: int
    vectors_upserted: int
    embedding_model: str
    embedding_dimension: int


def opportunity_point_id(opportunity_id: str) -> str:
    """Return the deterministic Qdrant point ID for a PostgreSQL opportunity."""
    if not opportunity_id:
        raise ValueError("opportunity_id is required")
    return str(uuid.uuid5(_UUID_NAMESPACE, f"opportunity:{opportunity_id}"))


def _skill_names(skills: Iterable[Any]) -> list[str]:
    return [skill.name for skill in skills if skill.name]


def build_opportunity_document(opportunity: Opportunity) -> OpportunityDocument:
    required_skills = _skill_names(opportunity.required_skills)
    preferred_skills = _skill_names(opportunity.preferred_skills)

    sections = [
        f"Title: {opportunity.title}",
        f"Company: {opportunity.company}",
        f"Target role: {opportunity.target_role}",
        f"Opportunity type: {opportunity.opportunity_type}",
        f"Experience level: {opportunity.experience_level or 'Not specified'}",
        f"Location: {opportunity.location or 'Not specified'}",
        f"Remote: {'Yes' if opportunity.is_remote else 'No'}",
        f"Industry: {opportunity.industry or 'Not specified'}",
        f"Description: {opportunity.description}",
        f"Required skills: {', '.join(required_skills)}",
        f"Preferred skills: {', '.join(preferred_skills)}",
    ]
    text = "\n".join(sections).strip()

    if not text or not opportunity.description or not opportunity.description.strip():
        raise OpportunityEmbeddingError(f"Opportunity {opportunity.id} cannot produce a valid document")
    if not required_skills:
        raise OpportunityEmbeddingError(f"Opportunity {opportunity.id} has no required skills")
    if not preferred_skills:
        raise OpportunityEmbeddingError(f"Opportunity {opportunity.id} has no preferred skills")

    payload = {
        "opportunity_id": opportunity.id,
        "title": opportunity.title,
        "company": opportunity.company,
        "target_role": opportunity.target_role,
        "opportunity_type": opportunity.opportunity_type,
        "location": opportunity.location,
        "is_remote": bool(opportunity.is_remote),
        "experience_level": opportunity.experience_level,
        "industry": opportunity.industry,
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
        "source": opportunity.source,
    }
    return OpportunityDocument(
        opportunity_id=opportunity.id,
        point_id=opportunity_point_id(opportunity.id),
        text=text,
        payload=payload,
    )


def _load_curated_opportunities(db: Session) -> list[Opportunity]:
    return (
        db.query(Opportunity)
        .options(
            joinedload(Opportunity.required_skills),
            joinedload(Opportunity.preferred_skills),
        )
        .filter(Opportunity.source == "curated")
        .order_by(Opportunity.title, Opportunity.company)
        .all()
    )


def ensure_opportunity_collection(collection_name: Optional[str] = None, vector_size: Optional[int] = None) -> str:
    collection = collection_name or settings.QDRANT_COLLECTION_OPPORTUNITIES
    ensure_collection(collection, vector_size=vector_size or get_embedding_dimension())
    return collection


def _validate_dimension(dimension: int, expected_dimension: Optional[int]) -> None:
    if expected_dimension is not None and dimension != expected_dimension:
        raise OpportunityEmbeddingError(
            f"Expected embedding dimension {expected_dimension}, got {dimension}"
        )


def _validate_vectors(vectors: Sequence[Sequence[float]], expected_count: int, dimension: int) -> None:
    if len(vectors) != expected_count:
        raise OpportunityEmbeddingError(f"Expected {expected_count} embeddings, got {len(vectors)}")
    for index, vector in enumerate(vectors, start=1):
        if not vector:
            raise OpportunityEmbeddingError(f"Embedding {index} is empty")
        if len(vector) != dimension:
            raise OpportunityEmbeddingError(
                f"Embedding {index} has dimension {len(vector)}, expected {dimension}"
            )


def _delete_stale_points(collection_name: str, current_point_ids: set[str]) -> None:
    client = get_qdrant_client()
    if not hasattr(client, "scroll"):
        return

    stale_ids: list[str] = []
    offset = None
    query_filter = qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="source",
                match=qmodels.MatchValue(value="curated"),
            )
        ]
    )
    while True:
        records, offset = client.scroll(
            collection_name=collection_name,
            scroll_filter=query_filter,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for record in records:
            if str(record.id) not in current_point_ids:
                stale_ids.append(str(record.id))
        if offset is None:
            break

    if stale_ids:
        delete_vectors(collection_name, stale_ids)


def index_curated_opportunities(
    db: Session,
    collection_name: Optional[str] = None,
    batch_size: int = 20,
    expected_dimension: Optional[int] = EXPECTED_EMBEDDING_DIMENSION,
    reconcile_stale: bool = True,
) -> OpportunityIndexingResult:
    collection = collection_name or settings.QDRANT_COLLECTION_OPPORTUNITIES
    dimension = get_embedding_dimension()
    _validate_dimension(dimension, expected_dimension)
    ensure_opportunity_collection(collection, vector_size=dimension)

    opportunities = _load_curated_opportunities(db)
    documents = [build_opportunity_document(opportunity) for opportunity in opportunities]
    if not documents:
        raise OpportunityEmbeddingError("No curated opportunities found to index")

    point_ids = {document.point_id for document in documents}
    if len(point_ids) != len(documents):
        raise OpportunityEmbeddingError("Duplicate opportunity point IDs generated")

    upserted = 0
    for batch_start in range(0, len(documents), batch_size):
        batch = documents[batch_start : batch_start + batch_size]
        vectors = embed_texts([document.text for document in batch])
        _validate_vectors(vectors, expected_count=len(batch), dimension=dimension)

        upsert_vectors(
            collection_name=collection,
            points=[
                {
                    "id": document.point_id,
                    "vector": vector,
                    "payload": document.payload,
                }
                for document, vector in zip(batch, vectors)
            ],
            vector_size=dimension,
        )
        upserted += len(batch)

    if reconcile_stale:
        _delete_stale_points(collection, point_ids)

    logger.info("[Opportunities] Indexed %d vectors into '%s'.", upserted, collection)
    return OpportunityIndexingResult(
        collection=collection,
        opportunities_found=len(opportunities),
        embeddings_generated=len(documents),
        vectors_upserted=upserted,
        embedding_model=settings.EMBEDDING_MODEL,
        embedding_dimension=dimension,
    )


def build_opportunity_filter(
    opportunity_type: Optional[str] = None,
    target_role: Optional[str] = None,
    is_remote: Optional[bool] = None,
    experience_level: Optional[str] = None,
    location: Optional[str] = None,
) -> Optional[qmodels.Filter]:
    conditions: list[qmodels.FieldCondition] = []
    values = {
        "opportunity_type": opportunity_type,
        "target_role": target_role,
        "is_remote": is_remote,
        "experience_level": experience_level,
        "location": location,
    }
    for key, value in values.items():
        if value is not None:
            conditions.append(
                qmodels.FieldCondition(
                    key=key,
                    match=qmodels.MatchValue(value=value),
                )
            )
    if not conditions:
        return None
    return qmodels.Filter(must=conditions)


def search_opportunities(
    query: str,
    limit: int = 10,
    collection_name: Optional[str] = None,
    opportunity_type: Optional[str] = None,
    target_role: Optional[str] = None,
    is_remote: Optional[bool] = None,
    experience_level: Optional[str] = None,
    location: Optional[str] = None,
):
    query_filter = build_opportunity_filter(
        opportunity_type=opportunity_type,
        target_role=target_role,
        is_remote=is_remote,
        experience_level=experience_level,
        location=location,
    )
    return semantic_search(
        collection_name=collection_name or settings.QDRANT_COLLECTION_OPPORTUNITIES,
        query_text=query,
        limit=limit,
        query_filter=query_filter,
    )
