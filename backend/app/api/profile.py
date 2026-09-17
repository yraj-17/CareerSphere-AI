import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db
from app.db.models import (
    CareerPreference,
    MediaObject,
    Profile,
    ProfileCertification,
    ProfileEducation,
    ProfileExperience,
    ProfileProject,
    ProfileSkill,
    ProjectTechnology,
    User,
)
from app.schemas.profile import (
    CareerPreferenceResponse,
    CareerPreferenceUpdate,
    CertificationCreate,
    CertificationResponse,
    CertificationUpdate,
    EducationCreate,
    EducationResponse,
    EducationUpdate,
    ExperienceCreate,
    ExperienceResponse,
    ExperienceUpdate,
    ProfileCompleteness,
    ProfilePhotoResponse,
    ProfileResponse,
    ProfileUpdate,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    SkillCreate,
    SkillResponse,
)
from app.services import storage_service
from app.services.career_matching_cache_service import invalidate_career_matching_cache

router = APIRouter(prefix="/profile", tags=["Profile"])


def _normalize_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _get_or_create_profile(db: Session, user: User) -> Profile:
    profile = (
        db.query(Profile)
        .options(
            selectinload(Profile.user),
            selectinload(Profile.profile_photo),
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
    if profile:
        return profile
    profile = Profile(user_id=user.id)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _get_or_create_profile(db, user)


def _get_item_or_404(db: Session, model, profile: Profile, item_id: str):
    item = db.query(model).filter(model.id == item_id, model.profile_id == profile.id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile item not found.")
    return item


def _commit(db: Session, message: str = "Failed to save profile data."):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate profile data is not allowed.")
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)


def _invalidate_matching_cache(user: User) -> None:
    invalidate_career_matching_cache(user.id)


def _text_from_list(values: list[str]) -> str:
    return json.dumps(values)


def _project_response(project: ProfileProject) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        technologies=[tech.name for tech in project.technologies],
        github_url=project.github_url,
        live_url=project.live_url,
        start_date=project.start_date,
        end_date=project.end_date,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _calculate_completeness(profile: Profile) -> ProfileCompleteness:
    checks = [
        ("Basic information", bool(profile.user.first_name and profile.user.last_name and profile.headline and profile.location and profile.about)),
        ("Skills", bool(profile.skills)),
        ("Education", bool(profile.education)),
        ("Experience", bool(profile.experience)),
        ("Projects", bool(profile.projects)),
        ("Certifications", bool(profile.certifications)),
        ("Career preferences", bool(profile.career_preferences and (profile.career_preferences.target_job_role or profile.career_preferences.preferred_industry or profile.career_preferences.preferred_work_type or profile.career_preferences.preferred_locations or profile.career_preferences.career_interests))),
    ]
    completed = [name for name, done in checks if done]
    missing = [name for name, done in checks if not done]
    return ProfileCompleteness(percentage=round((len(completed) / len(checks)) * 100), completed=completed, missing=missing)


def _profile_response(profile: Profile) -> ProfileResponse:
    photo = None
    if profile.profile_photo:
        try:
            photo_url = storage_service.presigned_get_url(profile.profile_photo.object_key)
        except Exception:
            photo_url = None
        photo = ProfilePhotoResponse(id=profile.profile_photo.id, url=photo_url)
    return ProfileResponse(
        id=profile.id,
        user=profile.user,
        headline=profile.headline,
        location=profile.location,
        about=profile.about,
        profile_photo_media_id=profile.profile_photo_media_id,
        profile_photo=photo,
        skills=profile.skills,
        education=profile.education,
        experience=profile.experience,
        projects=[_project_response(project) for project in profile.projects],
        certifications=profile.certifications,
        career_preferences=CareerPreferenceResponse.from_model(profile.career_preferences),
        completeness=_calculate_completeness(profile),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.get("/me", response_model=ProfileResponse)
def get_my_profile(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _profile_response(_get_or_create_profile(db, current_user))


@router.patch("/me", response_model=ProfileResponse)
@router.put("/me", response_model=ProfileResponse)
def update_my_profile(body: ProfileUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = _get_or_create_profile(db, current_user)
    data = body.model_dump(exclude_unset=True)
    for field in ("first_name", "last_name"):
        if field in data and data[field]:
            setattr(current_user, field, data[field])
    for field in ("headline", "location", "about"):
        if field in data:
            setattr(profile, field, data[field])
    if "profile_photo_media_id" in data:
        media_id = data["profile_photo_media_id"]
        if media_id:
            media = db.query(MediaObject).filter(MediaObject.id == media_id, MediaObject.user_id == current_user.id).first()
            if not media:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile photo was not found.")
            if media.purpose != "profile_image" or not media.content_type.startswith("image/"):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload a valid profile image first.")
        profile.profile_photo_media_id = media_id
    _commit(db)
    _invalidate_matching_cache(current_user)
    return _profile_response(_get_or_create_profile(db, current_user))


@router.get("/me/skills", response_model=list[SkillResponse])
def list_skills(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _get_or_create_profile(db, current_user).skills


@router.post("/me/skills", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
def add_skill(body: SkillCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = _get_or_create_profile(db, current_user)
    skill = ProfileSkill(profile_id=profile.id, name=body.name, normalized_name=_normalize_name(body.name))
    db.add(skill)
    _commit(db)
    _invalidate_matching_cache(current_user)
    db.refresh(skill)
    return skill


@router.delete("/me/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill(skill_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = _get_or_create_profile(db, current_user)
    db.delete(_get_item_or_404(db, ProfileSkill, profile, skill_id))
    _commit(db)
    _invalidate_matching_cache(current_user)


@router.get("/me/education", response_model=list[EducationResponse])
def list_education(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _get_or_create_profile(db, current_user).education


@router.post("/me/education", response_model=EducationResponse, status_code=status.HTTP_201_CREATED)
def add_education(body: EducationCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = _get_or_create_profile(db, current_user)
    item = ProfileEducation(profile_id=profile.id, **body.model_dump())
    db.add(item)
    _commit(db)
    db.refresh(item)
    return item


@router.put("/me/education/{item_id}", response_model=EducationResponse)
def update_education(item_id: str, body: EducationUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = _get_or_create_profile(db, current_user)
    item = _get_item_or_404(db, ProfileEducation, profile, item_id)
    for key, value in body.model_dump().items():
        setattr(item, key, value)
    _commit(db)
    db.refresh(item)
    return item


@router.delete("/me/education/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_education(item_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = _get_or_create_profile(db, current_user)
    db.delete(_get_item_or_404(db, ProfileEducation, profile, item_id))
    _commit(db)


@router.get("/me/experience", response_model=list[ExperienceResponse])
def list_experience(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _get_or_create_profile(db, current_user).experience


@router.post("/me/experience", response_model=ExperienceResponse, status_code=status.HTTP_201_CREATED)
def add_experience(body: ExperienceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = _get_or_create_profile(db, current_user)
    item = ProfileExperience(profile_id=profile.id, **body.model_dump())
    db.add(item)
    _commit(db)
    _invalidate_matching_cache(current_user)
    db.refresh(item)
    return item


@router.put("/me/experience/{item_id}", response_model=ExperienceResponse)
def update_experience(item_id: str, body: ExperienceUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = _get_or_create_profile(db, current_user)
    item = _get_item_or_404(db, ProfileExperience, profile, item_id)
    for key, value in body.model_dump().items():
        setattr(item, key, value)
    _commit(db)
    _invalidate_matching_cache(current_user)
    db.refresh(item)
    return item


@router.delete("/me/experience/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_experience(item_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = _get_or_create_profile(db, current_user)
    db.delete(_get_item_or_404(db, ProfileExperience, profile, item_id))
    _commit(db)
    _invalidate_matching_cache(current_user)


def _sync_project_technologies(project: ProfileProject, technologies: list[str]):
    project.technologies = [ProjectTechnology(name=name, normalized_name=_normalize_name(name)) for name in technologies]


@router.get("/me/projects", response_model=list[ProjectResponse])
def list_projects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return [_project_response(project) for project in _get_or_create_profile(db, current_user).projects]


@router.post("/me/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def add_project(body: ProjectCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = _get_or_create_profile(db, current_user)
    data = body.model_dump()
    technologies = data.pop("technologies", [])
    data["github_url"] = str(data["github_url"]) if data.get("github_url") else None
    data["live_url"] = str(data["live_url"]) if data.get("live_url") else None
    project = ProfileProject(profile_id=profile.id, **data)
    _sync_project_technologies(project, technologies)
    db.add(project)
    _commit(db)
    _invalidate_matching_cache(current_user)
    db.refresh(project)
    return _project_response(project)


@router.put("/me/projects/{item_id}", response_model=ProjectResponse)
def update_project(item_id: str, body: ProjectUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = _get_or_create_profile(db, current_user)
    project = _get_item_or_404(db, ProfileProject, profile, item_id)
    data = body.model_dump()
    technologies = data.pop("technologies", [])
    data["github_url"] = str(data["github_url"]) if data.get("github_url") else None
    data["live_url"] = str(data["live_url"]) if data.get("live_url") else None
    for key, value in data.items():
        setattr(project, key, value)
    _sync_project_technologies(project, technologies)
    _commit(db)
    _invalidate_matching_cache(current_user)
    db.refresh(project)
    return _project_response(project)


@router.delete("/me/projects/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(item_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = _get_or_create_profile(db, current_user)
    db.delete(_get_item_or_404(db, ProfileProject, profile, item_id))
    _commit(db)
    _invalidate_matching_cache(current_user)


@router.get("/me/certifications", response_model=list[CertificationResponse])
def list_certifications(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _get_or_create_profile(db, current_user).certifications


@router.post("/me/certifications", response_model=CertificationResponse, status_code=status.HTTP_201_CREATED)
def add_certification(body: CertificationCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = _get_or_create_profile(db, current_user)
    data = body.model_dump()
    data["credential_url"] = str(data["credential_url"]) if data.get("credential_url") else None
    item = ProfileCertification(profile_id=profile.id, **data)
    db.add(item)
    _commit(db)
    db.refresh(item)
    return item


@router.put("/me/certifications/{item_id}", response_model=CertificationResponse)
def update_certification(item_id: str, body: CertificationUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = _get_or_create_profile(db, current_user)
    item = _get_item_or_404(db, ProfileCertification, profile, item_id)
    data = body.model_dump()
    data["credential_url"] = str(data["credential_url"]) if data.get("credential_url") else None
    for key, value in data.items():
        setattr(item, key, value)
    _commit(db)
    db.refresh(item)
    return item


@router.delete("/me/certifications/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_certification(item_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = _get_or_create_profile(db, current_user)
    db.delete(_get_item_or_404(db, ProfileCertification, profile, item_id))
    _commit(db)


@router.get("/me/preferences", response_model=CareerPreferenceResponse)
def get_preferences(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = _get_or_create_profile(db, current_user)
    return CareerPreferenceResponse.from_model(profile.career_preferences)


@router.patch("/me/preferences", response_model=CareerPreferenceResponse)
@router.put("/me/preferences", response_model=CareerPreferenceResponse)
def update_preferences(body: CareerPreferenceUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = _get_or_create_profile(db, current_user)
    pref = profile.career_preferences or CareerPreference(profile_id=profile.id)
    data = body.model_dump()
    pref.target_job_role = data["target_job_role"]
    pref.preferred_industry = data["preferred_industry"]
    pref.preferred_work_type = data["preferred_work_type"]
    pref.preferred_locations = _text_from_list(data["preferred_locations"])
    pref.career_interests = _text_from_list(data["career_interests"])
    db.add(pref)
    _commit(db)
    _invalidate_matching_cache(current_user)
    db.refresh(pref)
    return CareerPreferenceResponse.from_model(pref)
