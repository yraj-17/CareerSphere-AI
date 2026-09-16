"""
Tests for Phase 3.3 opportunity embedding and Qdrant indexing.
"""

from __future__ import annotations

import os
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.db.models import Opportunity, OpportunityPreferredSkill, OpportunityRequiredSkill
from app.db.session import Base, SessionLocal, engine
from app.services import opportunity_embedding_service as service
from app.services import qdrant_service
from scripts.seed_opportunities import seed_curated_opportunities


@pytest.fixture(autouse=True)
def clean_curated_opportunities():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _delete_sources(db, {"curated", "phase-3-3-test"})
        db.commit()
    finally:
        db.close()

    yield

    db = SessionLocal()
    try:
        _delete_sources(db, {"curated", "phase-3-3-test"})
        db.commit()
    finally:
        db.close()


def _delete_sources(db, sources: set[str]) -> None:
    opportunity_ids = db.query(Opportunity.id).filter(Opportunity.source.in_(sources))
    db.query(OpportunityRequiredSkill).filter(
        OpportunityRequiredSkill.opportunity_id.in_(opportunity_ids)
    ).delete(synchronize_session=False)
    db.query(OpportunityPreferredSkill).filter(
        OpportunityPreferredSkill.opportunity_id.in_(opportunity_ids)
    ).delete(synchronize_session=False)
    db.query(Opportunity).filter(Opportunity.source.in_(sources)).delete(synchronize_session=False)


def _create_sample_opportunity(db) -> Opportunity:
    opp = Opportunity(
        title="Backend Engineer",
        company="Phase33 Labs",
        description=(
            "Build Python and FastAPI services for a SaaS platform, maintain PostgreSQL "
            "schemas, write tests, and collaborate with frontend engineers on reliable APIs."
        ),
        opportunity_type="job",
        target_role="Backend Engineer",
        location="Bengaluru, India",
        is_remote=False,
        experience_level="Junior",
        industry="SaaS",
        salary_min=700000,
        salary_max=1200000,
        application_url="https://careersphere.local/opportunities/sample",
        source="phase-3-3-test",
    )
    opp.required_skills.extend(
        [
            OpportunityRequiredSkill(name="Python", normalized_name="python"),
            OpportunityRequiredSkill(name="FastAPI", normalized_name="fastapi"),
            OpportunityRequiredSkill(name="PostgreSQL", normalized_name="postgresql"),
            OpportunityRequiredSkill(name="Git", normalized_name="git"),
        ]
    )
    opp.preferred_skills.extend(
        [
            OpportunityPreferredSkill(name="Docker", normalized_name="docker"),
            OpportunityPreferredSkill(name="Redis", normalized_name="redis"),
        ]
    )
    db.add(opp)
    db.commit()
    db.refresh(opp)
    return opp


def _fake_vectors(count: int, dim: int = 768) -> list[list[float]]:
    return [[float(index + 1) / 1000.0 for _ in range(dim)] for index in range(count)]


def test_opportunity_document_builder_contains_semantic_fields():
    db = SessionLocal()
    try:
        opp = _create_sample_opportunity(db)
        document = service.build_opportunity_document(opp)

        assert document.text
        assert "Backend Engineer" in document.text
        assert "Target role: Backend Engineer" in document.text
        assert opp.description in document.text
        assert "Required skills: FastAPI, Git, PostgreSQL, Python" in document.text
        assert "Preferred skills: Docker, Redis" in document.text
    finally:
        db.close()


def test_opportunity_payload_contains_retrieval_metadata():
    db = SessionLocal()
    try:
        opp = _create_sample_opportunity(db)
        payload = service.build_opportunity_document(opp).payload

        assert payload["opportunity_id"] == opp.id
        assert payload["target_role"] == "Backend Engineer"
        assert payload["required_skills"] == ["FastAPI", "Git", "PostgreSQL", "Python"]
        assert payload["preferred_skills"] == ["Docker", "Redis"]
        assert payload["source"] == "phase-3-3-test"
    finally:
        db.close()


def test_deterministic_point_ids_are_stable_and_distinct():
    point_a1 = service.opportunity_point_id("opportunity-a")
    point_a2 = service.opportunity_point_id("opportunity-a")
    point_b = service.opportunity_point_id("opportunity-b")

    assert point_a1 == point_a2
    assert point_a1 != point_b
    assert str(uuid.UUID(point_a1)) == point_a1


def test_embedding_dimension_is_expected_768(monkeypatch):
    monkeypatch.setattr(service, "get_embedding_dimension", lambda: 768)
    service._validate_dimension(service.get_embedding_dimension(), service.EXPECTED_EMBEDDING_DIMENSION)


def test_opportunity_collection_creation_is_idempotent(monkeypatch):
    calls = []
    monkeypatch.setattr(service, "get_embedding_dimension", lambda: 768)
    monkeypatch.setattr(service, "ensure_collection", lambda collection, vector_size: calls.append((collection, vector_size)))

    collection = service.ensure_opportunity_collection()
    service.ensure_opportunity_collection()

    assert collection == service.settings.QDRANT_COLLECTION_OPPORTUNITIES
    assert calls == [
        (service.settings.QDRANT_COLLECTION_OPPORTUNITIES, 768),
        (service.settings.QDRANT_COLLECTION_OPPORTUNITIES, 768),
    ]


def test_indexing_60_opportunities_upserts_60_vectors(monkeypatch):
    db = SessionLocal()
    captured = []
    try:
        seed_curated_opportunities(db)
        monkeypatch.setattr(service, "get_embedding_dimension", lambda: 768)
        monkeypatch.setattr(service, "ensure_collection", lambda collection, vector_size: None)
        monkeypatch.setattr(service, "embed_texts", lambda texts: _fake_vectors(len(texts)))
        monkeypatch.setattr(
            service,
            "upsert_vectors",
            lambda collection_name, points, vector_size: captured.extend(points),
        )

        result = service.index_curated_opportunities(db, reconcile_stale=False)

        assert result.opportunities_found == 60
        assert result.embeddings_generated == 60
        assert result.vectors_upserted == 60
        assert len(captured) == 60
        assert len({point["id"] for point in captured}) == 60
    finally:
        db.close()


def test_reindexing_uses_same_point_ids_without_duplicates(monkeypatch):
    db = SessionLocal()
    runs = []
    try:
        seed_curated_opportunities(db)
        monkeypatch.setattr(service, "get_embedding_dimension", lambda: 768)
        monkeypatch.setattr(service, "ensure_collection", lambda collection, vector_size: None)
        monkeypatch.setattr(service, "embed_texts", lambda texts: _fake_vectors(len(texts)))

        def capture(collection_name, points, vector_size):
            runs.append({point["id"] for point in points})

        monkeypatch.setattr(service, "upsert_vectors", capture)

        service.index_curated_opportunities(db, reconcile_stale=False)
        service.index_curated_opportunities(db, reconcile_stale=False)

        first_ids = set().union(*runs[:3])
        second_ids = set().union(*runs[3:])
        assert len(first_ids) == 60
        assert first_ids == second_ids
    finally:
        db.close()


def test_search_opportunities_returns_results_and_builds_filter(monkeypatch):
    scored = SimpleNamespace(
        payload={
            "title": "Backend Engineering Intern",
            "target_role": "Backend Engineer",
            "opportunity_type": "internship",
        },
        score=0.91,
    )
    captured = {}

    def fake_semantic_search(collection_name, query_text, limit, query_filter):
        captured.update(
            {
                "collection_name": collection_name,
                "query_text": query_text,
                "limit": limit,
                "query_filter": query_filter,
            }
        )
        return [scored]

    monkeypatch.setattr(service, "semantic_search", fake_semantic_search)

    results = service.search_opportunities(
        "Python backend development",
        limit=5,
        opportunity_type="internship",
        target_role="Backend Engineer",
        is_remote=True,
    )

    assert results[0].payload["target_role"] == "Backend Engineer"
    assert captured["collection_name"] == service.settings.QDRANT_COLLECTION_OPPORTUNITIES
    assert captured["limit"] == 5
    assert len(captured["query_filter"].must) == 3


def test_backend_and_devops_queries_can_return_relevant_payloads(monkeypatch):
    backend = SimpleNamespace(payload={"target_role": "Backend Engineer", "title": "Backend API Engineer"})
    devops = SimpleNamespace(payload={"target_role": "DevOps Engineer", "title": "DevOps Engineer"})

    def fake_semantic_search(collection_name, query_text, limit, query_filter):
        if "FastAPI" in query_text:
            return [backend]
        return [devops]

    monkeypatch.setattr(service, "semantic_search", fake_semantic_search)

    backend_results = service.search_opportunities("Python FastAPI backend developer", limit=3)
    devops_results = service.search_opportunities("AWS Docker Kubernetes infrastructure DevOps", limit=3)

    assert backend_results[0].payload["target_role"] == "Backend Engineer"
    assert devops_results[0].payload["target_role"] == "DevOps Engineer"


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_QDRANT_INTEGRATION") != "1",
    reason="Set RUN_QDRANT_INTEGRATION=1 and ensure Qdrant + Ollama embedding model are running.",
)
def test_real_opportunity_indexing_and_semantic_search():
    from app.services import embedding_service

    embedding_service.get_embedding_dimension.cache_clear()
    collection = f"career_opportunities_test_{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    client = qdrant_service.get_qdrant_client()
    try:
        seed_curated_opportunities(db)
        result = service.index_curated_opportunities(db, collection_name=collection, reconcile_stale=False)
        assert result.opportunities_found == 60
        assert result.embedding_dimension == 768

        count = client.count(collection_name=collection, exact=True).count
        assert count == 60

        results = service.search_opportunities(
            "Python FastAPI backend developer",
            limit=5,
            collection_name=collection,
        )
        assert results
        assert any(
            point.payload["target_role"] in {"Backend Engineer", "Full Stack Developer"}
            for point in results
        )
    finally:
        db.close()
        embedding_service.get_embedding_dimension.cache_clear()
        try:
            client.delete_collection(collection_name=collection)
        except Exception:
            pass
