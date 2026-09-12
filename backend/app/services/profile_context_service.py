import json
from datetime import date

from sqlalchemy.orm import Session, selectinload

from app.db.models import Profile, ProfileProject, User


def _format_date(value: date | None) -> str:
    if not value:
        return "Present"
    return value.strftime("%b %Y")


def _parse_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _line(label: str, value: str | None) -> str | None:
    if not value:
        return None
    return f"{label}: {value}"


def _bullets(title: str, values: list[str], limit: int = 8) -> list[str]:
    cleaned = [value.strip() for value in values if value and value.strip()]
    if not cleaned:
        return []
    return [f"{title}: {', '.join(cleaned[:limit])}"]


def get_profile_for_ai(db: Session, user: User) -> Profile | None:
    """Load the authenticated user's professional profile for AI context."""
    return (
        db.query(Profile)
        .options(
            selectinload(Profile.user),
            selectinload(Profile.skills),
            selectinload(Profile.education),
            selectinload(Profile.experience),
            selectinload(Profile.projects).selectinload(ProfileProject.technologies),
            selectinload(Profile.certifications),
            selectinload(Profile.career_preferences),
        )
        .filter(Profile.user_id == user.id)
        .first()
    )


def build_profile_context(db: Session, user: User) -> str:
    """
    Build compact, AI-friendly professional context from PostgreSQL.
    Excludes auth fields, internal IDs, secrets, and raw SQLAlchemy objects.
    """
    profile = get_profile_for_ai(db, user)
    lines = ["USER PROFILE CONTEXT", f"Name: {user.first_name} {user.last_name}".strip()]

    if not profile:
        lines.append("Profile status: No professional profile has been created yet.")
        return "\n".join(lines)

    basics = [
        _line("Headline", profile.headline),
        _line("Location", profile.location),
        _line("About", profile.about),
    ]
    lines.extend([item for item in basics if item])

    lines.extend(_bullets("Skills", [skill.name for skill in profile.skills], limit=16))

    education = []
    for item in profile.education[:4]:
        parts = [item.degree, item.field_of_study, item.institution]
        summary = " - ".join(part for part in parts if part)
        dates = f"{_format_date(item.start_date)} to {_format_date(item.end_date)}" if item.start_date or item.end_date else ""
        education.append(f"{summary} ({dates})" if dates else summary)
    lines.extend(_bullets("Education", education, limit=4))

    experience = []
    for item in profile.experience[:5]:
        dates = ""
        if item.start_date or item.end_date or item.currently_working:
            start = _format_date(item.start_date) if item.start_date else "Start date not listed"
            end = "Present" if item.currently_working else _format_date(item.end_date)
            dates = f"{start} to {end}"
        role = f"{item.job_title} at {item.company}"
        details = [role, item.employment_type, item.location, dates]
        experience.append(" | ".join(part for part in details if part))
    lines.extend(_bullets("Experience", experience, limit=5))

    projects = []
    for item in profile.projects[:5]:
        tech = ", ".join(technology.name for technology in item.technologies[:8])
        projects.append(f"{item.name}" + (f" ({tech})" if tech else ""))
    lines.extend(_bullets("Projects", projects, limit=5))

    certifications = [
        f"{item.name} by {item.issuing_organization}"
        for item in profile.certifications[:5]
    ]
    lines.extend(_bullets("Certifications", certifications, limit=5))

    prefs = profile.career_preferences
    if prefs:
        preferences = [
            _line("Target role", prefs.target_job_role),
            _line("Preferred industry", prefs.preferred_industry),
            _line("Preferred work type", prefs.preferred_work_type),
        ]
        lines.extend([item for item in preferences if item])
        lines.extend(_bullets("Preferred locations", _parse_list(prefs.preferred_locations), limit=8))
        lines.extend(_bullets("Career interests", _parse_list(prefs.career_interests), limit=10))

    if len(lines) <= 2:
        lines.append("Profile status: Professional profile exists but has limited information.")
    return "\n".join(lines)
