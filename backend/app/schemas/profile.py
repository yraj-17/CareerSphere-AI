import json
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


def _clean_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _normalize_list(values: Optional[list[str]]) -> list[str]:
    if not values:
        return []
    cleaned = []
    seen = set()
    for value in values:
        item = (value or "").strip()
        key = item.lower()
        if item and key not in seen:
            cleaned.append(item)
            seen.add(key)
    return cleaned


class DateRangeMixin(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    @model_validator(mode="after")
    def validate_date_order(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("Start date must be before end date.")
        return self


class UserSummary(BaseModel):
    id: str
    first_name: str
    last_name: str
    username: str
    email: str

    model_config = {"from_attributes": True}


class ProfileBase(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    headline: Optional[str] = Field(None, max_length=160)
    location: Optional[str] = Field(None, max_length=160)
    about: Optional[str] = Field(None, max_length=2000)
    profile_photo_media_id: Optional[str] = None

    @field_validator("first_name", "last_name", "headline", "location", "about", "profile_photo_media_id", mode="before")
    @classmethod
    def clean_strings(cls, value):
        return _clean_optional(value)


class ProfileUpdate(ProfileBase):
    pass


class ProfilePhotoResponse(BaseModel):
    id: str
    url: Optional[str] = None


class ProfileCompleteness(BaseModel):
    percentage: int
    completed: list[str]
    missing: list[str]


class SkillCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise ValueError("Skill name is required.")
        return value


class SkillResponse(BaseModel):
    id: str
    name: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EducationBase(DateRangeMixin):
    institution: str = Field(..., min_length=1, max_length=180)
    degree: str = Field(..., min_length=1, max_length=140)
    field_of_study: Optional[str] = Field(None, max_length=140)
    description: Optional[str] = Field(None, max_length=2000)

    @field_validator("institution", "degree", mode="before")
    @classmethod
    def clean_required(cls, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise ValueError("This field is required.")
        return value

    @field_validator("field_of_study", "description", mode="before")
    @classmethod
    def clean_optional_strings(cls, value):
        return _clean_optional(value)


class EducationCreate(EducationBase):
    pass


class EducationUpdate(EducationBase):
    pass


class EducationResponse(EducationBase):
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ExperienceBase(DateRangeMixin):
    company: str = Field(..., min_length=1, max_length=180)
    job_title: str = Field(..., min_length=1, max_length=160)
    employment_type: Optional[str] = Field(None, max_length=40)
    location: Optional[str] = Field(None, max_length=160)
    currently_working: bool = False
    description: Optional[str] = Field(None, max_length=2500)

    @field_validator("company", "job_title", mode="before")
    @classmethod
    def clean_required(cls, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise ValueError("This field is required.")
        return value

    @field_validator("employment_type", "location", "description", mode="before")
    @classmethod
    def clean_optional_strings(cls, value):
        return _clean_optional(value)

    @model_validator(mode="after")
    def normalize_current_role(self):
        if self.currently_working:
            self.end_date = None
        return self


class ExperienceCreate(ExperienceBase):
    pass


class ExperienceUpdate(ExperienceBase):
    pass


class ExperienceResponse(ExperienceBase):
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ProjectBase(DateRangeMixin):
    name: str = Field(..., min_length=1, max_length=180)
    description: Optional[str] = Field(None, max_length=2500)
    technologies: list[str] = Field(default_factory=list)
    github_url: Optional[HttpUrl] = None
    live_url: Optional[HttpUrl] = None

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise ValueError("Project name is required.")
        return value

    @field_validator("description", mode="before")
    @classmethod
    def clean_description(cls, value):
        return _clean_optional(value)

    @field_validator("technologies", mode="before")
    @classmethod
    def clean_technologies(cls, value):
        if isinstance(value, str):
            value = value.split(",")
        return _normalize_list(value)


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(ProjectBase):
    pass


class ProjectResponse(DateRangeMixin):
    id: str
    name: str
    description: Optional[str] = None
    technologies: list[str]
    github_url: Optional[str] = None
    live_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CertificationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=180)
    issuing_organization: str = Field(..., min_length=1, max_length=180)
    issue_date: Optional[date] = None
    expiration_date: Optional[date] = None
    credential_id: Optional[str] = Field(None, max_length=160)
    credential_url: Optional[HttpUrl] = None

    @field_validator("name", "issuing_organization", mode="before")
    @classmethod
    def clean_required(cls, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise ValueError("This field is required.")
        return value

    @field_validator("credential_id", mode="before")
    @classmethod
    def clean_optional_strings(cls, value):
        return _clean_optional(value)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.issue_date and self.expiration_date and self.issue_date > self.expiration_date:
            raise ValueError("Issue date must be before expiration date.")
        return self


class CertificationCreate(CertificationBase):
    pass


class CertificationUpdate(CertificationBase):
    pass


class CertificationResponse(BaseModel):
    id: str
    name: str
    issuing_organization: str
    issue_date: Optional[date] = None
    expiration_date: Optional[date] = None
    credential_id: Optional[str] = None
    credential_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CareerPreferenceUpdate(BaseModel):
    target_job_role: Optional[str] = Field(None, max_length=160)
    preferred_industry: Optional[str] = Field(None, max_length=160)
    preferred_work_type: Optional[str] = Field(None, max_length=80)
    preferred_locations: list[str] = Field(default_factory=list)
    career_interests: list[str] = Field(default_factory=list)

    @field_validator("target_job_role", "preferred_industry", "preferred_work_type", mode="before")
    @classmethod
    def clean_optional_strings(cls, value):
        return _clean_optional(value)

    @field_validator("preferred_locations", "career_interests", mode="before")
    @classmethod
    def clean_lists(cls, value):
        if isinstance(value, str):
            value = value.split(",")
        return _normalize_list(value)


class CareerPreferenceResponse(CareerPreferenceUpdate):
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, pref):
        if not pref:
            return cls()
        return cls(
            id=pref.id,
            target_job_role=pref.target_job_role,
            preferred_industry=pref.preferred_industry,
            preferred_work_type=pref.preferred_work_type,
            preferred_locations=json.loads(pref.preferred_locations or "[]"),
            career_interests=json.loads(pref.career_interests or "[]"),
            created_at=pref.created_at,
            updated_at=pref.updated_at,
        )


class ProfileResponse(BaseModel):
    id: str
    user: UserSummary
    headline: Optional[str] = None
    location: Optional[str] = None
    about: Optional[str] = None
    profile_photo_media_id: Optional[str] = None
    profile_photo: Optional[ProfilePhotoResponse] = None
    skills: list[SkillResponse]
    education: list[EducationResponse]
    experience: list[ExperienceResponse]
    projects: list[ProjectResponse]
    certifications: list[CertificationResponse]
    career_preferences: CareerPreferenceResponse
    completeness: ProfileCompleteness
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
