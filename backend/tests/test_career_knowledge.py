"""
Tests for Phase 1 — Multi-Domain Career Knowledge Base.

Test coverage
-------------
Unit tests (all mocked — no external services required):
  1.  Dataset loads successfully
  2.  All role IDs are unique
  3.  All skill IDs are unique
  4.  Role skill references are valid
  5.  Dataset contains multiple career domains
  6.  Dataset contains all 30 intended initial roles
  7.  Skill documents produce non-empty embedding text
  8.  Role documents produce non-empty embedding text
  9.  Embedding dimension reported by service matches expected size
  10. Qdrant payload contains correct metadata fields
  11. Qdrant point IDs are valid UUIDs
  12. Re-running indexing is idempotent (upsert called each time, same IDs)
  13. Semantic search returns a relevant role (mocked Qdrant)
  14. Semantic search returns a relevant skill (mocked Qdrant)
  15. Qdrant unavailable state is handled cleanly

Integration test (gated on RUN_QDRANT_INTEGRATION=1):
  16. Real end-to-end: dataset → embed → upsert → semantic search → payload
"""

from __future__ import annotations

import os
import uuid
from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import MagicMock, call, patch

import pytest

from app.data.career_knowledge import DOMAINS, ROLES, SKILLS, RoleEntry, SkillEntry
from app.services import embedding_service, qdrant_service
from app.services.career_indexing_service import (
    ValidationError,
    _UUID_NAMESPACE,
    _point_id,
    build_role_document,
    build_skill_document,
    initialize_career_knowledge,
    validate_career_dataset,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EXPECTED_ROLE_IDS = {
    "backend-engineer",
    "full-stack-developer",
    "frontend-developer",
    "devops-engineer",
    "cloud-engineer",
    "machine-learning-engineer",
    "data-scientist",
    "data-analyst",
    "product-manager",
    "business-analyst",
    "ui-ux-designer",
    "product-designer",
    "digital-marketing-specialist",
    "content-strategist",
    "financial-analyst",
    "accountant",
    "hr-specialist",
    "talent-acquisition-specialist",
    "sales-executive",
    "business-development-manager",
    "operations-manager",
    "supply-chain-analyst",
    "teacher-educator",
    "instructional-designer",
    "mechanical-engineer",
    "civil-engineer",
    "electrical-engineer",
    "healthcare-administrator",
    "compliance-analyst",
    "risk-analyst",
}

_FAKE_DIM = 4
_FAKE_VECTOR = [0.1, 0.2, 0.3, 0.4]


class _FakeEmbedClient:
    """Returns fixed-dimension fake vectors without calling Ollama."""

    def embed(self, model: str, input: List[str]):
        return {"embeddings": [_FAKE_VECTOR[:] for _ in input]}


# ---------------------------------------------------------------------------
# Test 1 — Dataset loads successfully
# ---------------------------------------------------------------------------


def test_dataset_loads_successfully():
    """DOMAINS, ROLES, and SKILLS are all non-empty and importable."""
    assert DOMAINS, "DOMAINS must not be empty"
    assert ROLES, "ROLES must not be empty"
    assert SKILLS, "SKILLS must not be empty"


# ---------------------------------------------------------------------------
# Test 2 — All role IDs are unique
# ---------------------------------------------------------------------------


def test_all_role_ids_are_unique():
    ids = [r.id for r in ROLES]
    assert len(ids) == len(set(ids)), f"Duplicate role IDs found: {[i for i in ids if ids.count(i) > 1]}"


# ---------------------------------------------------------------------------
# Test 3 — All skill IDs are unique
# ---------------------------------------------------------------------------


def test_all_skill_ids_are_unique():
    ids = list(SKILLS.keys())
    assert len(ids) == len(set(ids)), "Duplicate skill IDs in SKILLS dict"
    # Also verify dict keys match SkillEntry.id
    for key, skill in SKILLS.items():
        assert key == skill.id, f"Skill dict key '{key}' != skill.id '{skill.id}'"


# ---------------------------------------------------------------------------
# Test 4 — Role skill references are valid
# ---------------------------------------------------------------------------


def test_role_skill_references_are_valid():
    known = set(SKILLS.keys())
    errors = []
    for role in ROLES:
        for sid in role.required_skills:
            if sid not in known:
                errors.append(f"Role '{role.id}' required_skill '{sid}' not in SKILLS")
        for sid in role.recommended_skills:
            if sid not in known:
                errors.append(f"Role '{role.id}' recommended_skill '{sid}' not in SKILLS")
        overlap = set(role.required_skills) & set(role.recommended_skills)
        if overlap:
            errors.append(f"Role '{role.id}' has overlap between required/recommended: {overlap}")
    assert not errors, "\n".join(errors)


# ---------------------------------------------------------------------------
# Test 5 — Dataset contains multiple career domains
# ---------------------------------------------------------------------------


def test_dataset_contains_multiple_career_domains():
    assert len(DOMAINS) >= 14, f"Expected at least 14 domains, got {len(DOMAINS)}"
    role_domains = {r.domain for r in ROLES}
    # Every role domain should be declared in DOMAINS
    unknown = role_domains - set(DOMAINS)
    assert not unknown, f"Role domains not in DOMAINS list: {unknown}"


# ---------------------------------------------------------------------------
# Test 6 — Dataset contains all 30 intended initial roles
# ---------------------------------------------------------------------------


def test_dataset_contains_all_intended_roles():
    actual_ids = {r.id for r in ROLES}
    missing = _EXPECTED_ROLE_IDS - actual_ids
    unexpected = actual_ids - _EXPECTED_ROLE_IDS
    assert not missing, f"Missing expected role IDs: {sorted(missing)}"
    assert not unexpected, f"Unexpected role IDs (update _EXPECTED_ROLE_IDS if intentional): {sorted(unexpected)}"


# ---------------------------------------------------------------------------
# Test 7 — Skill documents produce non-empty embedding text
# ---------------------------------------------------------------------------


def test_skill_documents_produce_nonempty_embedding_text():
    for skill in SKILLS.values():
        text, payload = build_skill_document(skill)
        assert text.strip(), f"Skill '{skill.id}' produced empty embedding text"
        assert skill.name in text, f"Skill '{skill.id}' name not in text"
        assert skill.description.strip() in text or len(text) > 10


# ---------------------------------------------------------------------------
# Test 8 — Role documents produce non-empty embedding text
# ---------------------------------------------------------------------------


def test_role_documents_produce_nonempty_embedding_text():
    for role in ROLES:
        text, payload = build_role_document(role)
        assert text.strip(), f"Role '{role.id}' produced empty embedding text"
        assert role.name in text
        assert role.domain in text


# ---------------------------------------------------------------------------
# Test 9 — Embedding dimension matches configured/detected size
# ---------------------------------------------------------------------------


def test_embedding_dimension_matches_service(monkeypatch):
    embedding_service.get_embedding_dimension.cache_clear()
    monkeypatch.setattr(embedding_service, "get_embedding_client", lambda: _FakeEmbedClient())
    monkeypatch.setattr(embedding_service.settings, "EMBEDDING_DIMENSION", None)

    dim = embedding_service.get_embedding_dimension()
    assert dim == _FAKE_DIM

    # Each role/skill doc should produce a vector of that length
    text, _ = build_role_document(ROLES[0])
    vector = embedding_service.embed_text(text)
    assert len(vector) == _FAKE_DIM

    embedding_service.get_embedding_dimension.cache_clear()


# ---------------------------------------------------------------------------
# Test 10 — Qdrant payload contains correct metadata fields
# ---------------------------------------------------------------------------


def test_qdrant_payload_has_correct_metadata_fields():
    for role in ROLES:
        _, payload = build_role_document(role)
        assert payload["source_type"] == "role"
        assert payload["source_id"] == role.id
        assert "text" in payload
        meta = payload["metadata"]
        assert "name" in meta
        assert "domain" in meta
        assert "required_skills" in meta
        assert "recommended_skills" in meta
        assert isinstance(meta["required_skills"], list)
        assert isinstance(meta["recommended_skills"], list)

    for skill in SKILLS.values():
        _, payload = build_skill_document(skill)
        assert payload["source_type"] == "skill"
        assert payload["source_id"] == skill.id
        assert "text" in payload
        meta = payload["metadata"]
        assert "name" in meta
        assert "category" in meta
        assert "aliases" in meta


# ---------------------------------------------------------------------------
# Test 11 — Qdrant point IDs are valid UUIDs
# ---------------------------------------------------------------------------


def test_qdrant_point_ids_are_valid_uuids():
    for role in ROLES:
        pid = _point_id("role", role.id)
        parsed = uuid.UUID(pid)  # raises ValueError if invalid
        assert str(parsed) == pid

    for skill_id in SKILLS:
        pid = _point_id("skill", skill_id)
        parsed = uuid.UUID(pid)
        assert str(parsed) == pid


def test_point_ids_are_deterministic():
    """Same source_type + source_id must always produce the same UUID."""
    pid1 = _point_id("role", "backend-engineer")
    pid2 = _point_id("role", "backend-engineer")
    assert pid1 == pid2

    pid3 = _point_id("skill", "python")
    pid4 = _point_id("skill", "python")
    assert pid3 == pid4

    # Different inputs must produce different IDs
    assert _point_id("role", "backend-engineer") != _point_id("skill", "backend-engineer")
    assert _point_id("role", "backend-engineer") != _point_id("role", "data-scientist")


# ---------------------------------------------------------------------------
# Test 12 — Re-running indexing is idempotent
# ---------------------------------------------------------------------------


def test_rerunning_indexing_is_idempotent(monkeypatch):
    """
    Calling initialize_career_knowledge() twice should produce the exact same
    set of point IDs both times (upsert is an overwrite, not an insert).
    """
    embedding_service.get_embedding_dimension.cache_clear()
    monkeypatch.setattr(embedding_service, "get_embedding_client", lambda: _FakeEmbedClient())
    monkeypatch.setattr(embedding_service.settings, "EMBEDDING_DIMENSION", _FAKE_DIM)

    mock_client = MagicMock()
    mock_client.collection_exists.return_value = True
    monkeypatch.setattr(qdrant_service, "get_qdrant_client", lambda: mock_client)

    r1 = initialize_career_knowledge()
    r2 = initialize_career_knowledge()

    assert r1.total_vectors == r2.total_vectors
    assert r1.roles_indexed == r2.roles_indexed
    assert r1.skills_indexed == r2.skills_indexed

    # Both runs must have called upsert with the same point IDs
    all_calls = mock_client.upsert.call_args_list
    assert len(all_calls) >= 2  # at least one batch per run

    # Collect point IDs from first run and second run batches
    def _ids_from_calls(call_list):
        ids = set()
        for c in call_list:
            for pt in c.kwargs["points"]:
                ids.add(pt.id)
        return ids

    half = len(all_calls) // 2
    ids_run1 = _ids_from_calls(all_calls[:half])
    ids_run2 = _ids_from_calls(all_calls[half:])
    assert ids_run1 == ids_run2, "Point IDs changed between runs — not idempotent"

    embedding_service.get_embedding_dimension.cache_clear()


# ---------------------------------------------------------------------------
# Test 13 — Semantic search returns a relevant role (mocked)
# ---------------------------------------------------------------------------


def test_semantic_search_returns_relevant_role(monkeypatch):
    from qdrant_client.http import models as qmodels

    scored = qmodels.ScoredPoint(
        id=_point_id("role", "backend-engineer"),
        version=1,
        score=0.94,
        payload={
            "source_type": "role",
            "source_id": "backend-engineer",
            "text": "Backend Engineer: develops server-side APIs with Python and FastAPI.",
            "metadata": {
                "name": "Backend Engineer",
                "domain": "Software Engineering & Technology",
                "required_skills": ["Python", "FastAPI"],
                "recommended_skills": ["Docker"],
            },
        },
    )
    mock_client = MagicMock()
    mock_client.query_points.return_value = SimpleNamespace(points=[scored])
    monkeypatch.setattr(qdrant_service, "get_qdrant_client", lambda: mock_client)
    monkeypatch.setattr(qdrant_service, "embed_text", lambda text: _FAKE_VECTOR)

    from app.core.config import settings as cfg

    results = qdrant_service.semantic_search(
        cfg.QDRANT_COLLECTION_CONTENT,
        "server-side API development Python FastAPI",
        limit=1,
    )

    assert len(results) == 1
    assert results[0].payload["source_type"] == "role"
    assert results[0].payload["source_id"] == "backend-engineer"
    assert results[0].payload["metadata"]["domain"] == "Software Engineering & Technology"


# ---------------------------------------------------------------------------
# Test 14 — Semantic search returns a relevant skill (mocked)
# ---------------------------------------------------------------------------


def test_semantic_search_returns_relevant_skill(monkeypatch):
    from qdrant_client.http import models as qmodels

    scored = qmodels.ScoredPoint(
        id=_point_id("skill", "python"),
        version=1,
        score=0.97,
        payload={
            "source_type": "skill",
            "source_id": "python",
            "text": "Python: general-purpose programming language.",
            "metadata": {
                "name": "Python",
                "category": "programming",
                "aliases": ["Python 3"],
            },
        },
    )
    mock_client = MagicMock()
    mock_client.query_points.return_value = SimpleNamespace(points=[scored])
    monkeypatch.setattr(qdrant_service, "get_qdrant_client", lambda: mock_client)
    monkeypatch.setattr(qdrant_service, "embed_text", lambda text: _FAKE_VECTOR)

    from app.core.config import settings as cfg

    results = qdrant_service.semantic_search(
        cfg.QDRANT_COLLECTION_CONTENT,
        "Python programming language",
        limit=1,
    )

    assert len(results) == 1
    assert results[0].payload["source_type"] == "skill"
    assert results[0].payload["source_id"] == "python"
    assert results[0].payload["metadata"]["category"] == "programming"


# ---------------------------------------------------------------------------
# Test 15 — Qdrant unavailable state handled cleanly
# ---------------------------------------------------------------------------


def test_qdrant_unavailable_handled_cleanly(monkeypatch):
    """
    When Qdrant is down, initialize_career_knowledge() should raise an
    exception rather than silently fail or hang.
    """
    embedding_service.get_embedding_dimension.cache_clear()
    monkeypatch.setattr(embedding_service, "get_embedding_client", lambda: _FakeEmbedClient())
    monkeypatch.setattr(embedding_service.settings, "EMBEDDING_DIMENSION", _FAKE_DIM)

    class _DownClient:
        def collection_exists(self, collection_name):
            raise RuntimeError("connection refused")

        def create_collection(self, **kwargs):
            raise RuntimeError("connection refused")

    monkeypatch.setattr(qdrant_service, "get_qdrant_client", lambda: _DownClient())

    with pytest.raises(Exception, match="connection refused"):
        initialize_career_knowledge()

    embedding_service.get_embedding_dimension.cache_clear()


# ---------------------------------------------------------------------------
# Test 16 — Validation catches broken datasets
# ---------------------------------------------------------------------------


def test_validation_rejects_duplicate_role_id(monkeypatch):
    from app.services import career_indexing_service

    dup_roles = list(ROLES) + [ROLES[0]]  # duplicate the first role
    monkeypatch.setattr(career_indexing_service, "ROLES", dup_roles)

    with pytest.raises(ValidationError, match="Duplicate role IDs"):
        validate_career_dataset()


def test_validation_rejects_unknown_skill_reference(monkeypatch):
    from app.services import career_indexing_service

    bad_role = RoleEntry(
        id="bad-role",
        name="Bad Role",
        domain=DOMAINS[0],
        description="A role with a broken skill reference.",
        required_skills=["nonexistent-skill-xyz"],
        recommended_skills=[],
    )
    monkeypatch.setattr(career_indexing_service, "ROLES", list(ROLES) + [bad_role])

    with pytest.raises(ValidationError, match="not in SKILLS catalog"):
        validate_career_dataset()


def test_validation_rejects_required_recommended_overlap(monkeypatch):
    from app.services import career_indexing_service

    overlap_role = RoleEntry(
        id="overlap-role",
        name="Overlap Role",
        domain=DOMAINS[0],
        description="A role where python appears in both required and recommended.",
        required_skills=["python"],
        recommended_skills=["python"],
    )
    monkeypatch.setattr(career_indexing_service, "ROLES", list(ROLES) + [overlap_role])

    with pytest.raises(ValidationError, match="both required_skills and recommended_skills"):
        validate_career_dataset()


def test_validation_rejects_empty_description(monkeypatch):
    from app.services import career_indexing_service

    empty_desc_skill = {
        "empty-skill": SkillEntry(
            id="empty-skill",
            name="Empty Skill",
            category="test",
            description="   ",  # blank
        )
    }
    monkeypatch.setattr(
        career_indexing_service, "SKILLS", {**SKILLS, **empty_desc_skill}
    )

    with pytest.raises(ValidationError, match="empty description"):
        validate_career_dataset()


# ---------------------------------------------------------------------------
# Integration test — requires real Qdrant + Ollama
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_QDRANT_INTEGRATION") != "1",
    reason=(
        "Set RUN_QDRANT_INTEGRATION=1 and ensure Qdrant + Ollama "
        "with nomic-embed-text are running."
    ),
)
def test_real_career_knowledge_indexing_and_search():
    """
    Full end-to-end integration test:

        career dataset  →  embed (nomic-embed-text)  →  Qdrant  →  semantic search

    Uses a temporary isolated collection that is cleaned up after the test.
    """
    from app.services.career_indexing_service import initialize_career_knowledge
    from app.services import qdrant_service as qs
    from app.services import embedding_service as es

    es.get_embedding_dimension.cache_clear()
    test_collection = f"career_knowledge_test_{uuid.uuid4().hex[:8]}"

    try:
        # Index into a throwaway collection
        result = initialize_career_knowledge(collection_name=test_collection)

        assert result.roles_indexed == len(ROLES)
        assert result.skills_indexed == len(SKILLS)
        assert result.total_vectors == len(ROLES) + len(SKILLS)
        assert result.embedding_dimension == 768
        assert "nomic" in result.embedding_model.lower()

        # Verify the collection has the right number of points
        client = qs.get_qdrant_client()
        info = client.get_collection(collection_name=test_collection)
        assert info.points_count == len(ROLES) + len(SKILLS)

        # Semantic search — backend role
        results = qs.semantic_search(
            collection_name=test_collection,
            query_text="server-side API development Python FastAPI databases",
            limit=3,
        )
        source_ids = [r.payload["source_id"] for r in results]
        assert "backend-engineer" in source_ids, (
            f"Expected 'backend-engineer' in top results, got {source_ids}"
        )

        # Semantic search — python skill
        skill_results = qs.semantic_search(
            collection_name=test_collection,
            query_text="Python programming language scripting backend",
            limit=3,
        )
        skill_ids = [r.payload["source_id"] for r in skill_results]
        assert "python" in skill_ids, (
            f"Expected 'python' in top skill results, got {skill_ids}"
        )

        # Re-run indexing (idempotency check)
        result2 = initialize_career_knowledge(collection_name=test_collection)
        info2 = client.get_collection(collection_name=test_collection)
        assert info2.points_count == info.points_count, (
            "Point count changed after re-indexing — idempotency broken"
        )
        assert result2.total_vectors == result.total_vectors

        # Payload structure check on first result
        first = results[0]
        assert first.payload["source_type"] in ("role", "skill")
        assert "metadata" in first.payload
        assert "name" in first.payload["metadata"]

    finally:
        es.get_embedding_dimension.cache_clear()
        try:
            qs.get_qdrant_client().delete_collection(collection_name=test_collection)
        except Exception:
            pass
