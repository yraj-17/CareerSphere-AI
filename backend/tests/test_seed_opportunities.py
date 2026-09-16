"""
Tests for Phase 3.2 curated opportunity seeding.
"""

from __future__ import annotations

from collections import Counter

import pytest

from app.db.models import Opportunity, OpportunityPreferredSkill, OpportunityRequiredSkill
from app.db.session import Base, SessionLocal, engine
from scripts.seed_opportunities import (
    CURATED_OPPORTUNITIES,
    VALID_TARGET_ROLES,
    seed_curated_opportunities,
    validate_seed_dataset,
)


@pytest.fixture(autouse=True)
def clean_curated_opportunities():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _delete_sources(db, {"curated", "phase-3-2-test"})
        db.commit()
    finally:
        db.close()

    yield

    db = SessionLocal()
    try:
        _delete_sources(db, {"curated", "phase-3-2-test"})
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


def _seeded(db):
    return db.query(Opportunity).filter(Opportunity.source == "curated").all()


def test_seed_dataset_definition_is_valid():
    validate_seed_dataset()
    assert len(CURATED_OPPORTUNITIES) == 60


def test_seed_creates_exactly_60_curated_opportunities():
    db = SessionLocal()
    try:
        result = seed_curated_opportunities(db)
        opportunities = _seeded(db)

        assert result.inserted == 60
        assert result.curated_total == 60
        assert len(opportunities) == 60
        assert {opp.source for opp in opportunities} == {"curated"}
        assert {opp.external_id for opp in opportunities} == {None}
    finally:
        db.close()


def test_seed_is_idempotent_and_uses_stable_curated_identity():
    db = SessionLocal()
    try:
        first = seed_curated_opportunities(db)
        identities_first = {
            (opp.title, opp.company): opp.id
            for opp in db.query(Opportunity).filter(Opportunity.source == "curated").all()
        }

        second = seed_curated_opportunities(db)
        identities_second = {
            (opp.title, opp.company): opp.id
            for opp in db.query(Opportunity).filter(Opportunity.source == "curated").all()
        }

        assert first.inserted == 60
        assert second.inserted == 0
        assert second.updated == 60
        assert len(identities_second) == 60
        assert identities_second == identities_first
    finally:
        db.close()


def test_seed_creates_required_and_preferred_skills_without_duplicates_or_overlap():
    db = SessionLocal()
    try:
        seed_curated_opportunities(db)

        for opp in _seeded(db):
            required = [skill.normalized_name for skill in opp.required_skills]
            preferred = [skill.normalized_name for skill in opp.preferred_skills]

            assert required
            assert preferred
            assert len(required) == len(set(required))
            assert len(preferred) == len(set(preferred))
            assert not (set(required) & set(preferred))
            assert 4 <= len(required) <= 8
            assert 2 <= len(preferred) <= 5
    finally:
        db.close()


def test_seeded_opportunities_have_valid_roles_types_locations_levels_and_salary_ranges():
    db = SessionLocal()
    try:
        seed_curated_opportunities(db)
        opportunities = _seeded(db)

        assert {opp.target_role for opp in opportunities} <= VALID_TARGET_ROLES
        assert {"job", "internship"}.issubset({opp.opportunity_type for opp in opportunities})
        assert {False, True} == {opp.is_remote for opp in opportunities}
        assert len({opp.experience_level for opp in opportunities}) >= 4

        for opp in opportunities:
            assert opp.description and len(opp.description.strip()) >= 120
            assert opp.application_url.startswith("https://careersphere.local/opportunities/")
            if opp.salary_min is not None and opp.salary_max is not None:
                assert opp.salary_min <= opp.salary_max
    finally:
        db.close()


def test_reseeding_reconciles_skill_lists_exactly():
    db = SessionLocal()
    try:
        seed_curated_opportunities(db)
        opp = db.query(Opportunity).filter(Opportunity.source == "curated").first()

        db.add(
            OpportunityRequiredSkill(
                opportunity_id=opp.id,
                name="Temporary Skill",
                normalized_name="temporary-skill",
            )
        )
        db.add(
            OpportunityPreferredSkill(
                opportunity_id=opp.id,
                name="Temporary Preferred",
                normalized_name="temporary-preferred",
            )
        )
        db.commit()

        seed_curated_opportunities(db)
        db.refresh(opp)

        assert "temporary-skill" not in {skill.normalized_name for skill in opp.required_skills}
        assert "temporary-preferred" not in {skill.normalized_name for skill in opp.preferred_skills}
    finally:
        db.close()


def test_reseeding_does_not_modify_unrelated_non_curated_opportunities():
    db = SessionLocal()
    try:
        unrelated = Opportunity(
            title="Unrelated Backend Role",
            company="External Test Company",
            description="This non-curated opportunity should remain untouched by the curated seed.",
            opportunity_type="job",
            target_role="Backend Engineer",
            location="Delhi, India",
            is_remote=False,
            experience_level="Junior",
            industry="SaaS",
            salary_min=600000,
            salary_max=900000,
            application_url="https://example.test/job",
            source="phase-3-2-test",
            external_id="external-1",
        )
        db.add(unrelated)
        db.commit()
        unrelated_id = unrelated.id

        seed_curated_opportunities(db)
        seed_curated_opportunities(db)

        preserved = db.query(Opportunity).filter(Opportunity.id == unrelated_id).one()
        assert preserved.source == "phase-3-2-test"
        assert preserved.title == "Unrelated Backend Role"
        assert db.query(Opportunity).filter(Opportunity.source == "curated").count() == 60
    finally:
        db.close()


def test_expected_phase_3_2_distributions_are_present():
    db = SessionLocal()
    try:
        result = seed_curated_opportunities(db)
        opportunities = _seeded(db)

        assert result.role_distribution == dict(
            sorted(Counter(opp.target_role for opp in opportunities).items())
        )
        assert result.type_distribution == {"internship": 8, "job": 52}
        assert result.remote_distribution == {"non_remote": 41, "remote": 19}
        assert result.experience_distribution == {
            "Entry Level": 10,
            "Intern": 8,
            "Junior": 18,
            "Mid Level": 24,
        }
        assert result.required_skill_rows == 296
        assert result.preferred_skill_rows == 203
    finally:
        db.close()
