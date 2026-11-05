"""Deterministic matching of real job listings (in-memory objects; no DB, no AI)."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone

from app.data.job_taxonomy import canonical_skill_id, classify_role
from app.db.models import (
    CareerPreference,
    Opportunity,
    OpportunityRequiredSkill,
    Profile,
    ProfileEducation,
    ProfileExperience,
    ProfileProject,
    ProfileSkill,
    ProjectTechnology,
)
from app.services import career_matching_service as svc

NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)


def _profile(skills=("Python", "PostgreSQL", "Docker", "FastAPI"), target="Junior Python Developer",
             years: float = 0, work_type="Flexible", locations=("Pune",), location="Pune, India",
             project_tech=(), interests=(), education=None) -> Profile:
    profile = Profile(id="p1", user_id="u1", location=location)
    profile.skills = [ProfileSkill(name=s, normalized_name=s.lower()) for s in skills]
    project = ProfileProject(name="Side project")
    project.technologies = [ProjectTechnology(name=t, normalized_name=t.lower()) for t in project_tech]
    profile.projects = [project]
    profile.experience = []
    if years:
        start = date.today() - timedelta(days=int(years * 365))
        profile.experience = [ProfileExperience(company="Co", job_title="Developer", employment_type="Full-time",
                                                start_date=start, end_date=None, currently_working=True)]
    profile.education = education or []
    profile.career_preferences = CareerPreference(
        target_job_role=target, preferred_work_type=work_type,
        preferred_locations=json.dumps(list(locations)), career_interests=json.dumps(list(interests)),
    )
    return profile


def _job(title="Software Engineer - Backend", skills=("Python", "PostgreSQL", "Kafka"), location="Pune, India",
         work_mode="hybrid", min_years=None, max_years=None, level=None, employment="full_time",
         source="greenhouse", company="Acme", active=True, expires_at=None, country="India", description="") -> Opportunity:
    opp = Opportunity(
        id=str(uuid.uuid4()), title=title, company=company, description=description or f"{title} role.",
        opportunity_type="internship" if employment == "internship" else "job",
        target_role=(classify_role(title) or ["Other"])[0], location=location, is_remote=work_mode == "remote", work_mode=work_mode,
        experience_level=level, experience_min_years=min_years, experience_max_years=max_years, employment_type=employment,
        source=source, source_board="acme", country=country, is_active=active, expires_at=expires_at,
        application_url="https://jobs.example.org/apply", job_url="https://jobs.example.org/view",
        published_at=NOW - timedelta(days=2),
    )
    opp.required_skills = [OpportunityRequiredSkill(name=s, normalized_name=canonical_skill_id(s)) for s in skills]
    opp.preferred_skills = []
    return opp


def _rank(profile, jobs, filters=None):
    return svc.rank_listings(svc.profile_facts(profile), jobs, filters, now=NOW)


# ── Normalisation of the profile ─────────────────────────────────────────────

def test_profile_skills_are_normalised_and_comma_lists_split():
    profile = _profile(skills=["Python , Postgre, Mysql , node , express", "ReactJS"], project_tech=["K8s"])
    facts = svc.profile_facts(profile)
    assert {"python", "postgresql", "mysql", "nodejs", "express", "react", "kubernetes"} <= facts.skill_ids


def test_target_roles_are_normalised_to_families():
    assert svc.profile_facts(_profile(target="Backend and Devops")).target_roles == ["Backend Engineer", "DevOps Engineer"]
    assert svc.profile_facts(_profile(target="Junior Python Developer")).target_roles == ["Backend Engineer"]


# ── Equivalent titles / not overly restrictive ───────────────────────────────

def test_equivalent_title_is_a_match_for_junior_python_developer():
    run = _rank(_profile(), [_job(title="Software Engineer - Backend (Python)"), _job(title="SDE I, Payments API")])
    titles = [m.opportunity.title for m in run.matches]
    assert "Software Engineer - Backend (Python)" in titles
    assert "SDE I, Payments API" in titles  # generic software family is related, not excluded


def test_user_does_not_need_every_skill():
    run = _rank(_profile(skills=("Python",)), [_job(skills=("Python", "PostgreSQL", "Kafka", "Redis", "AWS"))])
    assert len(run.matches) == 1
    assert run.matches[0].matched_skills == ["Python"]
    assert set(run.matches[0].missing_skills) == {"PostgreSQL", "Kafka", "Redis", "AWS"}


def test_missing_optional_fields_do_not_exclude():
    job = _job(skills=(), location=None, work_mode=None, min_years=None, level=None, employment=None, country=None)
    run = _rank(_profile(), [job])
    assert len(run.matches) == 1
    breakdown = run.matches[0].result.breakdown
    assert breakdown.experience_match.relationship == "not_stated"
    assert breakdown.required_skill_score == svc.NEUTRAL  # unknown, not perfect


def test_missing_experience_is_not_ineligibility():
    run = _rank(_profile(years=0), [_job(min_years=None, level=None)])
    assert run.matches and "Experience requirement is not stated." in run.matches[0].reasons


# ── Hard eligibility vs scoring ──────────────────────────────────────────────

def test_far_senior_roles_are_ineligible_for_freshers_but_not_for_experienced():
    jobs = [_job(title="Staff Backend Engineer"), _job(title="Senior Backend Engineer"), _job(title="Backend Engineer", min_years=7)]
    assert _rank(_profile(years=0), jobs).excluded.get("far_above_experience") == 3
    assert len(_rank(_profile(years=6), jobs).matches) == 3


def test_inactive_and_expired_listings_are_excluded():
    run = _rank(_profile(), [_job(title="Backend Engineer A", active=False),
                             _job(title="Backend Engineer B", expires_at=NOW - timedelta(days=1)), _job(title="Backend Engineer C")])
    assert len(run.matches) == 1
    assert run.excluded["inactive"] == 1 and run.excluded["expired"] == 1


def test_unrelated_listing_is_not_a_match():
    run = _rank(_profile(), [_job(title="Account Executive, Enterprise Sales", skills=("CRM",))])
    assert run.matches == [] and run.excluded["low_relevance"] == 1


def test_scores_are_not_artificially_high():
    strong = _job(title="Backend Engineer", skills=("Python", "PostgreSQL", "Docker", "FastAPI"), level="Entry Level")
    weak = _job(title="Software Engineer", skills=("Java", "Spring Boot", "Kafka", "Kubernetes", "AWS", "Python"),
                location="Chennai, India", work_mode="onsite")
    run = _rank(_profile(), [strong, weak])
    by_title = {m.opportunity.title: m.result.final_score for m in run.matches}
    assert by_title["Backend Engineer"] >= 85
    assert by_title["Software Engineer"] < 65
    assert by_title["Software Engineer"] < by_title["Backend Engineer"]


def test_scoring_is_deterministic():
    jobs = [_job(title=f"Backend Engineer {i}") for i in range(5)]
    first = [(m.opportunity.id, m.result.final_score) for m in _rank(_profile(), jobs).matches]
    second = [(m.opportunity.id, m.result.final_score) for m in _rank(_profile(), jobs).matches]
    assert first == second


def test_explanation_reasons_are_concrete():
    match = _rank(_profile(), [_job(title="Backend Engineer", min_years=1, max_years=3)]).matches[0]
    joined = " ".join(match.reasons)
    assert "Title matches your target role (Backend Engineer)" in joined
    assert "You have 2 of the 3 skills" in joined
    assert "1–3 years" in joined
    assert match.result.breakdown.match_reasons == match.reasons


# ── Location / remote ────────────────────────────────────────────────────────

def test_location_preferences_affect_score_not_eligibility():
    pune = _job(title="Backend Engineer", location="Pune, India")
    delhi = _job(title="Backend Engineer", location="New Delhi, India")
    remote = _job(title="Backend Engineer", location="Remote - India", work_mode="remote")
    scores = {m.opportunity.location: m.result.breakdown.location_remote_score for m in _rank(_profile(), [pune, delhi, remote]).matches}
    assert scores["Pune, India"] == 100 and scores["Remote - India"] == 100
    assert scores["New Delhi, India"] < 100


def test_city_aliases_match():
    facts = svc.profile_facts(_profile(locations=("Bangalore",)))
    score, match = svc.location_score(facts, _job(location="Bengaluru, Karnataka"))
    assert score == 100 and match.relationship == "preferred_location"


def test_remote_preference_lowers_onsite_without_excluding():
    run = _rank(_profile(work_type="Remote"), [_job(title="Backend Engineer", work_mode="onsite")])
    assert run.matches and run.matches[0].result.breakdown.location_remote_score < 100


# ── Filters ──────────────────────────────────────────────────────────────────

def test_user_filters_are_applied():
    jobs = [_job(title="Backend Engineer", work_mode="remote", location="Remote"),
            _job(title="Backend Engineer", work_mode="onsite", location="Mumbai, India"),
            _job(title="Backend Intern", employment="internship", level="Intern", work_mode="onsite")]
    assert len(_rank(_profile(), jobs, svc.MatchFilters(work_mode="remote")).matches) == 1
    assert len(_rank(_profile(), jobs, svc.MatchFilters(location="Bombay")).matches) == 1  # alias
    assert len(_rank(_profile(), jobs, svc.MatchFilters(employment_type="internship")).matches) == 1
    assert len(_rank(_profile(), jobs, svc.MatchFilters(experience="internship")).matches) == 1
    run = _rank(_profile(), jobs, svc.MatchFilters(work_mode="hybrid"))
    assert run.matches == [] and run.excluded["filter_work_mode"] == 3


# ── Duplicates and preferences ───────────────────────────────────────────────

def test_cross_provider_duplicates_prefer_company_board():
    board = _job(title="Backend Engineer", source="greenhouse")
    agg = _job(title="Backend Engineer", source="adzuna")
    run = _rank(_profile(), [agg, board])
    assert len(run.matches) == 1 and run.matches[0].opportunity.source == "greenhouse"
    assert run.excluded["duplicate"] == 1


def test_education_and_interests_feed_preference_component():
    edu = [ProfileEducation(institution="X", degree="B.E.", field_of_study="Computer Engineering")]
    facts = svc.profile_facts(_profile(education=edu, interests=("payments",)))
    score, items = svc.preference_score(facts, _job(title="Backend Engineer", description="Build payments infrastructure"))
    assert score == 100 and {i.dimension for i in items} == {"education", "career_interests"}


def test_no_target_role_still_matches_on_skills():
    run = _rank(_profile(target=None), [_job(title="Platform Developer", skills=("Python", "PostgreSQL", "Docker"))])
    assert len(run.matches) == 1


def test_incomplete_profile_detected():
    assert svc.profile_facts(_profile(skills=(), target=None)).is_complete is False


def test_inactive_duplicate_never_shadows_active_copy():
    run = _rank(_profile(), [_job(title="Backend Engineer", source="greenhouse", active=False),
                             _job(title="Backend Engineer", source="adzuna")])
    assert len(run.matches) == 1 and run.matches[0].opportunity.source == "adzuna"


# ── Cybersecurity analyst profile (presentation-audit regressions) ──────────

def _cyber_profile():
    return _profile(
        skills=("Cybersecurity Fundamentals", "Network Security", "Computer Networking", "Cryptography", "Linux",
                "TCP/IP", "Wireshark", "Nmap"),
        target="Cybersecurity Analyst", locations=("Pune",), project_tech=("DNS", "Networking Fundamentals."))


def test_cybersecurity_analyst_profile_is_normalised():
    facts = svc.profile_facts(_cyber_profile())
    assert facts.target_roles == ["Security Analyst"]
    assert {"security", "network_security", "networking", "cryptography", "linux", "wireshark", "nmap"} <= facts.skill_ids


def test_infrastructure_and_generic_swe_roles_are_not_related_to_security_analyst():
    jobs = [_job(title="Infrastructure Engineer", skills=("Linux", "Kubernetes", "Python")),
            _job(title="Software Development Engineer Intern", skills=(), employment="internship", level="Intern")]
    run = _rank(_cyber_profile(), jobs)
    assert run.matches == [] and run.excluded["low_relevance"] == 2


def test_security_roles_rank_for_cybersecurity_analyst():
    soc = _job(title="SOC Analyst L1", skills=("Network Security", "SIEM", "Incident Response", "Wireshark"), level="Entry Level")
    detection = _job(title="Threat Detection Engineer", skills=("Linux", "Network Security"), min_years=2, max_years=6)
    infra = _job(title="Infrastructure Engineer", skills=("Linux",))
    run = _rank(_cyber_profile(), [infra, detection, soc])
    assert {m.opportunity.title for m in run.matches} == {"SOC Analyst L1", "Threat Detection Engineer"}
    detection_match = next(m for m in run.matches if m.opportunity.title == "Threat Detection Engineer")
    # The stated 2–6 year requirement is visible in the score and the reasons, not hidden.
    assert detection_match.result.breakdown.experience_score == 50
    assert any("2–6 years" in reason for reason in detection_match.reasons)


def test_generic_analyst_word_is_not_a_role_match():
    run = _rank(_cyber_profile(), [_job(title="Payments Analyst", skills=("SQL",))])
    assert run.matches == []


def test_industry_preference_with_multiple_parts_matches_any_part():
    profile = _cyber_profile()
    profile.career_preferences.preferred_industry = "Information Technology / Cybersecurity"
    facts = svc.profile_facts(profile)
    score, items = svc.preference_score(facts, _job(title="SOC Analyst", description="Protect us from cybersecurity threats"))
    industry = next(i for i in items if i.dimension == "industry")
    assert industry.matched is True
