import uuid
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, BigInteger, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    media_objects = relationship("MediaObject", back_populates="owner", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="owner", cascade="all, delete-orphan")
    profile = relationship("Profile", back_populates="user", cascade="all, delete-orphan", uselist=False)

    def __repr__(self):
        return f"<User username={self.username} email={self.email}>"


class MediaObject(Base):
    """
    Relational metadata for files stored in MinIO.
    Binary content lives in object storage; only keys/metadata live here.
    """

    __tablename__ = "media_objects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    object_key = Column(String(512), unique=True, nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(128), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    purpose = Column(String(50), nullable=False, default="general", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    owner = relationship("User", back_populates="media_objects")
    profile_photo_for = relationship("Profile", back_populates="profile_photo", uselist=False)

    def __repr__(self):
        return f"<MediaObject id={self.id} key={self.object_key} purpose={self.purpose}>"


class Conversation(Base):
    """Persistent AI chat thread owned by a single user."""

    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(120), nullable=False, default="New conversation")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    owner = relationship("User", back_populates="conversations")
    messages = relationship(
        "ChatMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )

    def __repr__(self):
        return f"<Conversation id={self.id} user_id={self.user_id}>"


class ChatMessage(Base):
    """A single user or assistant turn within a conversation."""

    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    conversation_id = Column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    # Records whether the user's CareerSphere profile was included in the LLM
    # prompt that produced this assistant message. Always False for user turns.
    used_profile_context = Column(Boolean, nullable=False, server_default="false", default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self):
        return f"<ChatMessage id={self.id} role={self.role}>"


class Profile(Base):
    """Professional profile extension for a user."""

    __tablename__ = "profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    profile_photo_media_id = Column(String(36), ForeignKey("media_objects.id", ondelete="SET NULL"), nullable=True)
    headline = Column(String(160), nullable=True)
    location = Column(String(160), nullable=True)
    about = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="profile")
    profile_photo = relationship("MediaObject", back_populates="profile_photo_for")
    skills = relationship("ProfileSkill", back_populates="profile", cascade="all, delete-orphan", order_by="ProfileSkill.name")
    education = relationship("ProfileEducation", back_populates="profile", cascade="all, delete-orphan", order_by="ProfileEducation.start_date.desc().nullslast()")
    experience = relationship("ProfileExperience", back_populates="profile", cascade="all, delete-orphan", order_by="ProfileExperience.start_date.desc().nullslast()")
    projects = relationship("ProfileProject", back_populates="profile", cascade="all, delete-orphan", order_by="ProfileProject.start_date.desc().nullslast()")
    certifications = relationship("ProfileCertification", back_populates="profile", cascade="all, delete-orphan", order_by="ProfileCertification.issue_date.desc().nullslast()")
    career_preferences = relationship("CareerPreference", back_populates="profile", cascade="all, delete-orphan", uselist=False)


class ProfileSkill(Base):
    __tablename__ = "profile_skills"
    __table_args__ = (UniqueConstraint("profile_id", "normalized_name", name="uq_profile_skill_name"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    profile_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(80), nullable=False)
    normalized_name = Column(String(80), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    profile = relationship("Profile", back_populates="skills")


class ProfileEducation(Base):
    __tablename__ = "profile_education"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    profile_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    institution = Column(String(180), nullable=False)
    degree = Column(String(140), nullable=False)
    field_of_study = Column(String(140), nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    profile = relationship("Profile", back_populates="education")


class ProfileExperience(Base):
    __tablename__ = "profile_experience"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    profile_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    company = Column(String(180), nullable=False)
    job_title = Column(String(160), nullable=False)
    employment_type = Column(String(40), nullable=True)
    location = Column(String(160), nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    currently_working = Column(Boolean, nullable=False, default=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    profile = relationship("Profile", back_populates="experience")


class ProfileProject(Base):
    __tablename__ = "profile_projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    profile_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(180), nullable=False)
    description = Column(Text, nullable=True)
    github_url = Column(String(500), nullable=True)
    live_url = Column(String(500), nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    profile = relationship("Profile", back_populates="projects")
    technologies = relationship("ProjectTechnology", back_populates="project", cascade="all, delete-orphan", order_by="ProjectTechnology.name")


class ProjectTechnology(Base):
    __tablename__ = "project_technologies"
    __table_args__ = (UniqueConstraint("project_id", "normalized_name", name="uq_project_technology_name"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    project_id = Column(String(36), ForeignKey("profile_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(80), nullable=False)
    normalized_name = Column(String(80), nullable=False)

    project = relationship("ProfileProject", back_populates="technologies")


class ProfileCertification(Base):
    __tablename__ = "profile_certifications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    profile_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(180), nullable=False)
    issuing_organization = Column(String(180), nullable=False)
    issue_date = Column(Date, nullable=True)
    expiration_date = Column(Date, nullable=True)
    credential_id = Column(String(160), nullable=True)
    credential_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    profile = relationship("Profile", back_populates="certifications")


class CareerPreference(Base):
    __tablename__ = "career_preferences"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    profile_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    target_job_role = Column(String(160), nullable=True)
    preferred_industry = Column(String(160), nullable=True)
    preferred_work_type = Column(String(80), nullable=True)
    preferred_locations = Column(Text, nullable=True)
    career_interests = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    profile = relationship("Profile", back_populates="career_preferences")


class Opportunity(Base):
    """A career opportunity (job, internship, etc.) that can be matched to user profiles."""

    __tablename__ = "opportunities"
    __table_args__ = (
        Index(
            "uq_opportunity_source_external_id",
            "source",
            "external_id",
            unique=True,
            postgresql_where=Column("external_id") != None,  # noqa: E711
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    title = Column(String(200), nullable=False)
    company = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    opportunity_type = Column(String(50), nullable=False, index=True)
    target_role = Column(String(160), nullable=False, index=True)
    location = Column(String(160), nullable=True, index=True)
    is_remote = Column(Boolean, nullable=False, default=False, index=True)
    experience_level = Column(String(80), nullable=True, index=True)
    industry = Column(String(160), nullable=True)
    salary_min = Column(BigInteger, nullable=True)
    salary_max = Column(BigInteger, nullable=True)
    application_url = Column(String(500), nullable=True)
    source = Column(String(80), nullable=False, index=True)
    external_id = Column(String(255), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    required_skills = relationship("OpportunityRequiredSkill", back_populates="opportunity", cascade="all, delete-orphan", order_by="OpportunityRequiredSkill.name")
    preferred_skills = relationship("OpportunityPreferredSkill", back_populates="opportunity", cascade="all, delete-orphan", order_by="OpportunityPreferredSkill.name")

    def __repr__(self):
        return f"<Opportunity id={self.id} title={self.title} source={self.source}>"


class OpportunityRequiredSkill(Base):
    __tablename__ = "opportunity_required_skills"
    __table_args__ = (UniqueConstraint("opportunity_id", "normalized_name", name="uq_opportunity_required_skill_name"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    opportunity_id = Column(String(36), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(80), nullable=False)
    normalized_name = Column(String(80), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    opportunity = relationship("Opportunity", back_populates="required_skills")


class OpportunityPreferredSkill(Base):
    __tablename__ = "opportunity_preferred_skills"
    __table_args__ = (UniqueConstraint("opportunity_id", "normalized_name", name="uq_opportunity_preferred_skill_name"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    opportunity_id = Column(String(36), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(80), nullable=False)
    normalized_name = Column(String(80), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    opportunity = relationship("Opportunity", back_populates="preferred_skills")
