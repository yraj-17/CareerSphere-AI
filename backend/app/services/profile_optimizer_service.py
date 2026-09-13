import json
import re
from datetime import date
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.models import User
from app.schemas.ai import ProfileOptimizationResponse
from app.services import ollama_service, profile_context_service
from app.services.ollama_service import AIServiceError


SYSTEM_PROMPT = """You are CareerSphere AI, a professional career profile optimization assistant.

Analyze the provided CareerSphere profile.
Treat all profile information as user-provided facts.
Never invent facts about the user.
Separate existing facts from recommendations.
Identify strengths, weaknesses, missing information, clarity issues, and actionable improvements.
Recommendations should align with the user's stated career goals and existing background.
If suggesting a skill, clearly label it as a skill to learn or recommendation, not as an existing user skill.
Do not claim hiring probability, interview probability, recruiter ranking, or guaranteed employability.
Return only valid JSON matching the requested schema. Do not include markdown, prose outside JSON, or comments."""


USER_PROMPT = """Analyze this CareerSphere profile and return valid JSON with this exact shape:
{
  "overall_score": 0-100,
  "summary": "short profile quality summary",
  "sections": [
    {
      "section": "headline|about|skills|experience|education|projects|certifications|career_preferences",
      "score": 0-100,
      "status": "strong|needs_improvement|missing",
      "current": "existing profile information or null",
      "suggestion": "specific actionable suggestion",
      "reason": "why this improves the profile"
    }
  ],
  "strengths": ["facts-backed strengths only"],
  "recommended_improvements": ["actionable improvements"],
  "existing_skills": ["only skills present in profile.skills"],
  "suggested_skills_to_learn": ["recommended skills not present in profile.skills"]
}

Rules:
- Score profile quality only, not hiring probability.
- Do not invent skills, companies, projects, roles, certifications, education, dates, years, or achievements.
- existing_skills must contain only exact skills listed under profile.skills.
- suggested_skills_to_learn must not duplicate existing skills.
- If a section is empty, mark it missing and recommend how to improve it.
- Keep the response concise.

USER PROFILE JSON:
{profile_json}"""


def _date(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _parse_list(value: str | None) -> list[str]:
    return profile_context_service._parse_list(value)


def _compact_list(values: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return values[:limit]


def build_profile_payload(db: Session, user: User) -> dict[str, Any]:
    profile = profile_context_service.get_profile_for_ai(db, user)
    payload: dict[str, Any] = {
        "basic": {
            "name": f"{user.first_name} {user.last_name}".strip(),
        },
        "skills": [],
        "education": [],
        "experience": [],
        "projects": [],
        "certifications": [],
        "career_preferences": {},
    }
    if not profile:
        payload["profile_status"] = "No professional profile has been created yet."
        return payload

    payload["basic"].update(
        {
            "headline": profile.headline,
            "location": profile.location,
            "about": profile.about,
        }
    )
    payload["skills"] = [skill.name for skill in profile.skills[:24]]
    payload["education"] = _compact_list(
        [
            {
                "institution": item.institution,
                "degree": item.degree,
                "field_of_study": item.field_of_study,
                "start_date": _date(item.start_date),
                "end_date": _date(item.end_date),
                "description": item.description,
            }
            for item in profile.education
        ],
        6,
    )
    payload["experience"] = _compact_list(
        [
            {
                "company": item.company,
                "job_title": item.job_title,
                "employment_type": item.employment_type,
                "location": item.location,
                "start_date": _date(item.start_date),
                "end_date": _date(item.end_date),
                "currently_working": item.currently_working,
                "description": item.description,
            }
            for item in profile.experience
        ],
        6,
    )
    payload["projects"] = _compact_list(
        [
            {
                "name": item.name,
                "description": item.description,
                "technologies": [technology.name for technology in item.technologies[:10]],
                "start_date": _date(item.start_date),
                "end_date": _date(item.end_date),
            }
            for item in profile.projects
        ],
        6,
    )
    payload["certifications"] = _compact_list(
        [
            {
                "name": item.name,
                "issuing_organization": item.issuing_organization,
                "issue_date": _date(item.issue_date),
                "expiration_date": _date(item.expiration_date),
            }
            for item in profile.certifications
        ],
        6,
    )
    prefs = profile.career_preferences
    if prefs:
        payload["career_preferences"] = {
            "target_job_role": prefs.target_job_role,
            "preferred_industry": prefs.preferred_industry,
            "preferred_work_type": prefs.preferred_work_type,
            "preferred_locations": _parse_list(prefs.preferred_locations),
            "career_interests": _parse_list(prefs.career_interests),
        }
    return payload


def _extract_json_object(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise AIServiceError("The AI model returned an unexpected response.")
        try:
            parsed = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise AIServiceError("The AI model returned an unexpected response.") from exc
    if not isinstance(parsed, dict):
        raise AIServiceError("The AI model returned an unexpected response.")
    return parsed


def _normalize_skill(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _sanitize_response(
    result: ProfileOptimizationResponse,
    actual_skills: list[str],
) -> ProfileOptimizationResponse:
    actual_by_key = {_normalize_skill(skill): skill for skill in actual_skills}
    existing = []
    for skill in result.existing_skills:
        key = _normalize_skill(skill)
        if key in actual_by_key and actual_by_key[key] not in existing:
            existing.append(actual_by_key[key])

    suggested = []
    seen = set()
    for skill in result.suggested_skills_to_learn:
        key = _normalize_skill(skill)
        if key and key not in actual_by_key and key not in seen:
            suggested.append(skill.strip())
            seen.add(key)

    return result.model_copy(
        update={
            "existing_skills": existing or actual_skills,
            "suggested_skills_to_learn": suggested,
        }
    )


async def optimize_profile(db: Session, user: User) -> ProfileOptimizationResponse:
    profile_payload = build_profile_payload(db, user)
    profile_json = json.dumps(profile_payload, ensure_ascii=True, separators=(",", ":"))
    try:
        content = await ollama_service.generate_response(
            prompt=USER_PROMPT.replace("{profile_json}", profile_json),
            system_prompt=SYSTEM_PROMPT,
            think=False,
        )
        parsed = _extract_json_object(content)
        result = ProfileOptimizationResponse.model_validate(parsed)
    except AIServiceError:
        raise
    except (ValidationError, KeyError, TypeError, ValueError) as exc:
        raise AIServiceError("The AI model returned an unexpected response.") from exc

    return _sanitize_response(result, profile_payload.get("skills", []))
