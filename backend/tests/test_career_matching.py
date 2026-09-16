"""Tests for Phase 3.4 deterministic career matching."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

from app.db.models import (
    CareerPreference,
    Opportunity,
    OpportunityPreferredSkill,
    OpportunityRequiredSkill,
    Profile,
    ProfileExperience,
    ProfileProject,
    ProfileSkill,
    ProjectTechnology,
)
from app.services import career_matching_service as svc


def _profile(
    skills: list[str] | None = None,
    target_role: str | None = "Backend Engineer",
    preferred_industry: str | None = None,
    preferred_work_type: str | None = None,
    preferred_locations: list[str] | None = None,
    location: str | None = "Mumbai, India",
    experience_level: str = "Entry Level",
) -> Profile:
    profile = Profile(id="profile-1", user_id="user-1", location=location)
    profile.skills = [
        ProfileSkill(name=name, normalized_name=name.lower().replace(" ", "-"))
        for name in (skills or [])
    ]
    project = ProfileProject(name="CareerSphere AI")
    project.technologies = []
    profile.projects = [project]
    profile.education = []
    profile.experience = []
    if experience_level == "Intern":
        profile.experience = [
            ProfileExperience(
                company="Demo",
                job_title="Software Intern",
                employment_type="Internship",
                start_date=datetime.now(timezone.utc).date().replace(year=datetime.now(timezone.utc).year - 1),
                end_date=datetime.now(timezone.utc).date().replace(month=1),
            )
        ]
    elif experience_level == "Junior":
        profile.experience = [
            ProfileExperience(
                company="Demo",
                job_title="Software Engineer",
                employment_type="Full-time",
                start_date=datetime.now(timezone.utc).date().replace(year=datetime.now(timezone.utc).year - 2),
                end_date=datetime.now(timezone.utc).date(),
            )
        ]
    elif experience_level == "Mid Level":
        profile.experience = [
            ProfileExperience(
                company="Demo",
                job_title="Software Engineer",
                employment_type="Full-time",
                start_date=datetime.now(timezone.utc).date().replace(year=datetime.now(timezone.utc).year - 4),
                end_date=datetime.now(timezone.utc).date(),
            )
        ]

    if any(value is not None for value in [target_role, preferred_industry, preferred_work_type, preferred_locations]):
        profile.career_preferences = CareerPreference(
            target_job_role=target_role,
            preferred_industry=preferred_industry,
            preferred_work_type=preferred_work_type,
            preferred_locations=json.dumps(preferred_locations or []),
        )
    else:
        profile.career_preferences = None
    return profile


def _opportunity(
    id: str = "opp-1",
    required: list[str] | None = None,
    preferred: list[str] | None = None,
    target_role: str = "Backend Engineer",
    opportunity_type: str = "job",
    is_remote: bool = False,
    location: str = "Mumbai, India",
    experience_level: str = "Entry Level",
    industry: str = "SaaS",
    expires_at=None,
) -> Opportunity:
    opp = Opportunity(
        id=id,
        title=f"{target_role} {id}",
        company="DemoCo",
        description="Build realistic product features with a cross-functional engineering team.",
        opportunity_type=opportunity_type,
        target_role=target_role,
        location=location,
        is_remote=is_remote,
        experience_level=experience_level,
        industry=industry,
        source="test",
        expires_at=expires_at,
    )
    opp.required_skills = [
        OpportunityRequiredSkill(name=name, normalized_name=name.lower().replace(" ", "-"))
        for name in (required or [])
    ]
    opp.preferred_skills = [
        OpportunityPreferredSkill(name=name, normalized_name=name.lower().replace(" ", "-"))
        for name in (preferred or [])
    ]
    return opp


def test_required_skill_calculation_4_of_6_is_66_67():
    profile = _profile(skills=["Python", "FastAPI", "PostgreSQL", "Docker"])
    opp = _opportunity(required=["Python", "FastAPI", "PostgreSQL", "Docker", "AWS", "Kubernetes"])

    score, summary = svc.calculate_required_skill_score(opp, svc.extract_user_skill_keys(profile))

    assert score == 66.67
    assert summary.matched == ["Python", "FastAPI", "PostgreSQL", "Docker"]
    assert summary.missing == ["AWS", "Kubernetes"]


def test_preferred_skill_calculation_2_of_4_is_50():
    profile = _profile(skills=["Redis", "AWS"])
    opp = _opportunity(preferred=["Redis", "AWS", "Kubernetes", "GraphQL"])

    score, summary = svc.calculate_preferred_skill_score(opp, svc.extract_user_skill_keys(profile))

    assert score == 50.0
    assert summary.matched == ["Redis", "AWS"]


def test_zero_preferred_skills_scores_100():
    profile = _profile(skills=["Python"])
    opp = _opportunity(preferred=[])

    score, summary = svc.calculate_preferred_skill_score(opp, svc.extract_user_skill_keys(profile))

    assert score == 100.0
    assert summary.matched == []
    assert summary.missing == []


def test_target_role_exact_strong_partial_and_unrelated_scores():
    exact, _ = svc.role_relationship_score("Backend Engineer", "Backend Engineer")
    strong, _ = svc.role_relationship_score("Backend Engineer", "Full Stack Developer")
    partial, _ = svc.role_relationship_score("Backend Engineer", "Cloud Engineer")
    unrelated, _ = svc.role_relationship_score("Backend Engineer", "Accountant")

    assert exact == 100.0
    assert strong == 75.0
    assert partial == 50.0
    assert unrelated == 0.0


def test_multiple_target_roles_use_best_applicable_score():
    opp = _opportunity(target_role="Cloud Engineer")

    score, match = svc.calculate_target_role_score(["Backend Engineer", "DevOps Engineer"], opp)

    assert score == 75.0
    assert "DevOps Engineer" in match.relationship


def test_experience_exact_and_adjacent_scores():
    exact, exact_match = svc.calculate_experience_score("Entry Level", "Entry Level")
    adjacent, adjacent_match = svc.calculate_experience_score("Entry Level", "Junior")

    assert exact == 100.0
    assert exact_match.relationship == "exact"
    assert adjacent == 75.0
    assert adjacent_match.relationship == "adjacent"


def test_remote_preference_and_no_work_mode_preference_score_100():
    remote_opp = _opportunity(is_remote=True, location="Remote - India")

    remote_profile = _profile(preferred_work_type="Remote")
    neutral_profile = _profile(preferred_work_type=None)

    assert svc.calculate_location_remote_score(remote_profile, remote_opp)[0] == 100.0
    assert svc.calculate_location_remote_score(neutral_profile, remote_opp)[0] == 100.0


def test_preferred_location_match_scores_100():
    profile = _profile(preferred_locations=["mumbai"])
    opp = _opportunity(location="Mumbai, India", is_remote=False)

    score, location_match = svc.calculate_location_remote_score(profile, opp)

    assert score == 100.0
    assert location_match.relationship == "preferred_location_match"


def test_remote_only_hard_filter_excludes_onsite_opportunity():
    profile = _profile(preferred_work_type="Remote only")
    onsite = _opportunity(is_remote=False)

    include, reason = svc.apply_hard_filters(profile, onsite)

    assert include is False
    assert reason == "remote_only_required"


def test_expired_opportunity_is_excluded():
    profile = _profile()
    expired = _opportunity(expires_at=datetime.now(timezone.utc) - timedelta(days=1))

    include, reason = svc.apply_hard_filters(profile, expired)

    assert include is False
    assert reason == "expired"


def test_missing_and_no_career_preferences_do_not_penalize():
    missing_pref_profile = _profile(target_role=None, preferred_industry=None, preferred_work_type=None, preferred_locations=[])
    no_pref_profile = _profile(target_role=None, preferred_industry=None, preferred_work_type=None, preferred_locations=None)
    no_pref_profile.career_preferences = None
    opp = _opportunity()

    assert svc.calculate_career_preference_score(missing_pref_profile, opp)[0] == 100.0
    assert svc.calculate_career_preference_score(no_pref_profile, opp)[0] == 100.0


def test_final_weighted_score_uses_exact_phase_3_4_weights():
    score = svc.calculate_final_score(
        required_skill_score=66.67,
        preferred_skill_score=50,
        target_role_score=100,
        experience_score=75,
        location_remote_score=100,
        career_preference_score=80,
    )

    assert score == 74.83


def test_deterministic_sorting_uses_score_required_score_then_id():
    profile = _profile(skills=["Python", "FastAPI"], target_role="Backend Engineer")
    opp_b = _opportunity(id="b", required=["Python", "FastAPI"], preferred=[], target_role="Backend Engineer")
    opp_a = _opportunity(id="a", required=["Python", "FastAPI"], preferred=[], target_role="Backend Engineer")

    first = svc.rank_opportunities(profile, [opp_b, opp_a])
    second = svc.rank_opportunities(profile, [opp_b, opp_a])

    assert [result.opportunity_id for result in first] == ["a", "b"]
    assert [result.opportunity_id for result in first] == [result.opportunity_id for result in second]


def test_top_10_limit_from_30_candidates():
    profile = _profile(skills=["Python"], target_role="Backend Engineer")
    candidates = [
        _opportunity(id=f"opp-{index:02d}", required=["Python"], preferred=[], target_role="Backend Engineer")
        for index in range(30)
    ]

    response = svc.match_opportunities(profile, candidates, limit=10)

    assert response.candidates_considered == 30
    assert response.candidates_after_filters == 30
    assert len(response.results) == 10


def test_skill_normalization_matches_equivalent_aliases():
    profile = _profile(skills=["Postgres", "React.js"])
    opp = _opportunity(required=["PostgreSQL", "React"])

    score, summary = svc.calculate_required_skill_score(opp, svc.extract_user_skill_keys(profile))

    assert score == 100.0
    assert summary.missing == []


def test_full_end_to_end_service_ranks_realistic_backend_match_first():
    profile = _profile(
        skills=["Python", "FastAPI", "Postgres", "Docker", "Git"],
        target_role="Backend Engineer",
        preferred_industry="SaaS",
        preferred_work_type="Remote",
        preferred_locations=["Mumbai"],
        experience_level="Entry Level",
    )
    backend = _opportunity(
        id="backend",
        required=["Python", "FastAPI", "PostgreSQL", "Docker"],
        preferred=["Redis", "AWS"],
        target_role="Backend Engineer",
        is_remote=True,
        location="Remote - India",
        industry="SaaS",
        experience_level="Junior",
    )
    frontend = _opportunity(
        id="frontend",
        required=["React", "TypeScript", "CSS", "HTML"],
        preferred=["Next.js", "Figma"],
        target_role="Frontend Developer",
        is_remote=False,
        location="Chennai, India",
        industry="Media",
        experience_level="Mid Level",
    )
    cloud = _opportunity(
        id="cloud",
        required=["AWS", "Terraform", "Linux", "Docker"],
        preferred=["Kubernetes", "Security"],
        target_role="Cloud Engineer",
        is_remote=True,
        location="Remote - India",
        industry="Cloud Computing",
        experience_level="Junior",
    )

    response = svc.match_opportunities(profile, [frontend, cloud, backend])

    assert response.results[0].opportunity_id == "backend"
    assert response.results[0].breakdown.required_skill_score == 100.0
    assert response.results[0].breakdown.target_role_score == 100.0
    assert response.results[0].breakdown.missing_preferred_skills == ["Redis", "AWS"]
