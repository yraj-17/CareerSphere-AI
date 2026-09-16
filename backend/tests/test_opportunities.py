"""
Opportunity model tests against PostgreSQL (no SQLite).

Requires Docker infrastructure:
  docker compose up -d postgres
and a valid DATABASE_URL in the environment or .env.
"""
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import Opportunity, OpportunityRequiredSkill, OpportunityPreferredSkill
from app.db.session import Base, SessionLocal, engine


@pytest.fixture(autouse=True)
def clean_opportunity_data():
    """Ensure tables exist and remove leftover test opportunity data."""
    Base.metadata.create_all(bind=engine)
    yield
    db = SessionLocal()
    try:
        db.query(OpportunityRequiredSkill).filter(
            OpportunityRequiredSkill.opportunity_id.in_(
                db.query(Opportunity.id).filter(Opportunity.source == "test")
            )
        ).delete(synchronize_session=False)
        db.query(OpportunityPreferredSkill).filter(
            OpportunityPreferredSkill.opportunity_id.in_(
                db.query(Opportunity.id).filter(Opportunity.source == "test")
            )
        ).delete(synchronize_session=False)
        db.query(Opportunity).filter(Opportunity.source == "test").delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _make_opportunity(**overrides) -> Opportunity:
    """Create an Opportunity instance with sensible defaults (source='test')."""
    defaults = dict(
        title="Backend Engineer",
        company="Acme Corp",
        description="Build scalable APIs.",
        opportunity_type="job",
        target_role="Backend Engineer",
        source="test",
        is_remote=False,
    )
    defaults.update(overrides)
    return Opportunity(**defaults)


# ── 1. Create an opportunity ──────────────────────────────────────────────

def test_create_opportunity():
    db = SessionLocal()
    try:
        opp = _make_opportunity()
        db.add(opp)
        db.commit()
        db.refresh(opp)
        assert opp.id is not None
        assert len(opp.id) == 36
        assert opp.title == "Backend Engineer"
        assert opp.is_remote is False
        assert opp.created_at is not None
        assert opp.updated_at is not None
    finally:
        db.close()


# ── 2. Required skills can be attached ────────────────────────────────────

def test_attach_required_skills():
    db = SessionLocal()
    try:
        opp = _make_opportunity()
        opp.required_skills.append(
            OpportunityRequiredSkill(name="Python", normalized_name="python")
        )
        opp.required_skills.append(
            OpportunityRequiredSkill(name="FastAPI", normalized_name="fastapi")
        )
        db.add(opp)
        db.commit()
        db.refresh(opp)
        assert len(opp.required_skills) == 2
        names = {s.normalized_name for s in opp.required_skills}
        assert names == {"python", "fastapi"}
    finally:
        db.close()


# ── 3. Preferred skills can be attached ───────────────────────────────────

def test_attach_preferred_skills():
    db = SessionLocal()
    try:
        opp = _make_opportunity()
        opp.preferred_skills.append(
            OpportunityPreferredSkill(name="Docker", normalized_name="docker")
        )
        db.add(opp)
        db.commit()
        db.refresh(opp)
        assert len(opp.preferred_skills) == 1
        assert opp.preferred_skills[0].normalized_name == "docker"
    finally:
        db.close()


# ── 4. normalized_name uniqueness per opportunity ─────────────────────────

def test_required_skill_unique_per_opportunity():
    db = SessionLocal()
    try:
        opp = _make_opportunity()
        opp.required_skills.append(
            OpportunityRequiredSkill(name="Python", normalized_name="python")
        )
        db.add(opp)
        db.commit()

        dup = OpportunityRequiredSkill(
            opportunity_id=opp.id, name="python", normalized_name="python"
        )
        db.add(dup)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()


def test_preferred_skill_unique_per_opportunity():
    db = SessionLocal()
    try:
        opp = _make_opportunity()
        opp.preferred_skills.append(
            OpportunityPreferredSkill(name="Docker", normalized_name="docker")
        )
        db.add(opp)
        db.commit()

        dup = OpportunityPreferredSkill(
            opportunity_id=opp.id, name="Docker", normalized_name="docker"
        )
        db.add(dup)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()


# ── 5. Same skill on different opportunities ──────────────────────────────

def test_same_skill_on_different_opportunities():
    db = SessionLocal()
    try:
        opp_a = _make_opportunity(title="Role A")
        opp_a.required_skills.append(
            OpportunityRequiredSkill(name="Python", normalized_name="python")
        )
        opp_b = _make_opportunity(title="Role B")
        opp_b.required_skills.append(
            OpportunityRequiredSkill(name="Python", normalized_name="python")
        )
        db.add_all([opp_a, opp_b])
        db.commit()
        assert opp_a.required_skills[0].normalized_name == "python"
        assert opp_b.required_skills[0].normalized_name == "python"
        assert opp_a.required_skills[0].id != opp_b.required_skills[0].id
    finally:
        db.close()


# ── 6. Opportunity with both required and preferred skills ────────────────

def test_opportunity_with_both_skill_types():
    db = SessionLocal()
    try:
        opp = _make_opportunity()
        opp.required_skills.append(
            OpportunityRequiredSkill(name="Python", normalized_name="python")
        )
        opp.preferred_skills.append(
            OpportunityPreferredSkill(name="Docker", normalized_name="docker")
        )
        db.add(opp)
        db.commit()
        db.refresh(opp)
        assert len(opp.required_skills) == 1
        assert len(opp.preferred_skills) == 1
    finally:
        db.close()


# ── 7. Cascade delete → required skills removed ──────────────────────────

def test_cascade_delete_required_skills():
    db = SessionLocal()
    try:
        opp = _make_opportunity()
        opp.required_skills.append(
            OpportunityRequiredSkill(name="Go", normalized_name="go")
        )
        db.add(opp)
        db.commit()
        opp_id = opp.id

        db.delete(opp)
        db.commit()

        remaining = (
            db.query(OpportunityRequiredSkill)
            .filter(OpportunityRequiredSkill.opportunity_id == opp_id)
            .count()
        )
        assert remaining == 0
    finally:
        db.close()


# ── 8. Cascade delete → preferred skills removed ─────────────────────────

def test_cascade_delete_preferred_skills():
    db = SessionLocal()
    try:
        opp = _make_opportunity()
        opp.preferred_skills.append(
            OpportunityPreferredSkill(name="Kubernetes", normalized_name="kubernetes")
        )
        db.add(opp)
        db.commit()
        opp_id = opp.id

        db.delete(opp)
        db.commit()

        remaining = (
            db.query(OpportunityPreferredSkill)
            .filter(OpportunityPreferredSkill.opportunity_id == opp_id)
            .count()
        )
        assert remaining == 0
    finally:
        db.close()


# ── 9. source + external_id uniqueness for non-null IDs ──────────────────

def test_source_external_id_unique():
    db = SessionLocal()
    try:
        opp_a = _make_opportunity(external_id="ext-123")
        db.add(opp_a)
        db.commit()

        opp_b = _make_opportunity(title="Duplicate", external_id="ext-123")
        db.add(opp_b)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()


# ── 10. Multiple curated opportunities with NULL external_id ──────────────

def test_multiple_null_external_ids_allowed():
    db = SessionLocal()
    try:
        opp_a = _make_opportunity(title="Curated A", external_id=None)
        opp_b = _make_opportunity(title="Curated B", external_id=None)
        opp_c = _make_opportunity(title="Curated C", external_id=None)
        db.add_all([opp_a, opp_b, opp_c])
        db.commit()

        count = (
            db.query(Opportunity)
            .filter(Opportunity.source == "test", Opportunity.external_id.is_(None))
            .count()
        )
        assert count >= 3
    finally:
        db.close()
