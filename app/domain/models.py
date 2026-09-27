from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def normalize_code(value: str) -> str:
    return value.strip().casefold()


class UuidPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class VersionMixin:
    version: Mapped[int] = mapped_column(default=1, nullable=False)


class AuditColumnsMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security.users.id"), nullable=True
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security.users.id"), nullable=True
    )


class User(UuidPrimaryKeyMixin, AuditColumnsMixin, VersionMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ux_users_entra_object_id", "entra_object_id", unique=True),
        Index("ix_users_email", "email"),
        {"schema": "security"},
    )

    entra_object_id: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    resource: Mapped[Resource | None] = relationship(
        back_populates="user", foreign_keys="Resource.user_id"
    )


class Project(UuidPrimaryKeyMixin, AuditColumnsMixin, VersionMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("length(trim(code)) > 0", name="ck_projects_code_not_blank"),
        CheckConstraint("length(trim(name)) > 0", name="ck_projects_name_not_blank"),
        CheckConstraint(
            "start_date IS NULL OR target_end_date IS NULL OR target_end_date >= start_date",
            name="ck_projects_target_end_after_start",
        ),
        CheckConstraint(
            "start_date IS NULL OR actual_end_date IS NULL OR actual_end_date >= start_date",
            name="ck_projects_actual_end_after_start",
        ),
        Index("ux_projects_code_normalized", "code_normalized", unique=True),
        Index("ix_projects_lifecycle_state", "lifecycle_state"),
        Index("ix_projects_project_type", "project_type"),
        Index("ix_projects_delivery_model", "delivery_model"),
        {"schema": "portfolio"},
    )

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    code_normalized: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    business_area: Mapped[str] = mapped_column(String(40), nullable=False)
    project_type: Mapped[str] = mapped_column(String(40), nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(String(40), nullable=False)
    priority: Mapped[str] = mapped_column(String(40), nullable=False)
    delivery_model: Mapped[str] = mapped_column(String(40), nullable=False)
    edpx_card_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    jira_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    confluence_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    figma_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    allocations: Mapped[list[Allocation]] = relationship(back_populates="project")
    dependencies: Mapped[list[ProjectDependency]] = relationship(back_populates="project")
    key_people: Mapped[list[ProjectStakeholder]] = relationship(back_populates="project")
    partners: Mapped[list[ProjectPartner]] = relationship(back_populates="project")
    sprints: Mapped[list[Sprint]] = relationship(back_populates="project")


class PartnerCompany(UuidPrimaryKeyMixin, AuditColumnsMixin, VersionMixin, Base):
    __tablename__ = "partner_companies"
    __table_args__ = (Index("ux_partner_companies_name_normalized", "name_normalized", unique=True), {"schema": "portfolio"})
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    projects: Mapped[list[ProjectPartner]] = relationship(back_populates="partner")


class ProjectPartner(UuidPrimaryKeyMixin, AuditColumnsMixin, VersionMixin, Base):
    __tablename__ = "project_partners"
    __table_args__ = (Index("ux_project_partners_project_partner", "project_id", "partner_company_id", unique=True), {"schema": "portfolio"})
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("portfolio.projects.id"), nullable=False)
    partner_company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("portfolio.partner_companies.id"), nullable=False)
    contribution_description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    contribution_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    project: Mapped[Project] = relationship(back_populates="partners")
    partner: Mapped[PartnerCompany] = relationship(back_populates="projects")


class Sprint(UuidPrimaryKeyMixin, AuditColumnsMixin, VersionMixin, Base):
    __tablename__ = "sprints"
    __table_args__ = (Index("ux_sprints_project_number", "project_id", "sprint_number", unique=True), {"schema": "portfolio"})
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("portfolio.projects.id"), nullable=False)
    sprint_number: Mapped[int] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    goal: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    project: Mapped[Project] = relationship(back_populates="sprints")


class Skill(UuidPrimaryKeyMixin, AuditColumnsMixin, VersionMixin, Base):
    __tablename__ = "skills"
    __table_args__ = (Index("ux_skills_name_normalized", "name_normalized", unique=True), {"schema": "resource"})
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    resource_skills: Mapped[list[ResourceSkill]] = relationship(back_populates="skill")


class ResourceSkill(UuidPrimaryKeyMixin, AuditColumnsMixin, VersionMixin, Base):
    __tablename__ = "resource_skills"
    __table_args__ = (Index("ux_resource_skills_resource_skill", "resource_id", "skill_id", unique=True), {"schema": "resource"})
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("resource.resources.id"), nullable=False)
    skill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("resource.skills.id"), nullable=False)
    level: Mapped[int] = mapped_column(nullable=False)
    resource: Mapped[Resource] = relationship(back_populates="skills")
    skill: Mapped[Skill] = relationship(back_populates="resource_skills")


class ProjectDependency(UuidPrimaryKeyMixin, AuditColumnsMixin, VersionMixin, Base):
    __tablename__ = "project_dependencies"
    __table_args__ = (
        CheckConstraint(
            "length(trim(title)) > 0", name="ck_project_dependencies_title_not_blank"
        ),
        CheckConstraint(
            "length(trim(description)) > 0",
            name="ck_project_dependencies_description_not_blank",
        ),
        CheckConstraint(
            "target_date >= start_date", name="ck_project_dependencies_target_after_start"
        ),
        CheckConstraint(
            "(status = 'RESOLVED' AND resolved_date IS NOT NULL AND resolved_date >= start_date) "
            "OR (status <> 'RESOLVED' AND resolved_date IS NULL)",
            name="ck_project_dependencies_resolved_state",
        ),
        Index(
            "ux_project_dependencies_project_title",
            "project_id",
            "title_normalized",
            unique=True,
        ),
        Index("ix_project_dependencies_project_status", "project_id", "status"),
        Index("ix_project_dependencies_impact_status", "impact_level", "status"),
        {"schema": "portfolio"},
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolio.projects.id"), nullable=False
    )
    owner_key_person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolio.key_people.id"), nullable=True
    )
    dependency_type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    title_normalized: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="OPEN", nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    resolved_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    impact_level: Mapped[str] = mapped_column(String(20), nullable=False)
    mitigation_plan: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    external_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)

    project: Mapped[Project] = relationship(back_populates="dependencies")
    owner: Mapped[KeyPerson | None] = relationship()

    @property
    def is_open(self) -> bool:
        return self.status in {"OPEN", "IN_PROGRESS", "BLOCKED"}

    @property
    def is_overdue(self) -> bool:
        return self.is_open and self.target_date < date.today()

    @property
    def is_critical_open(self) -> bool:
        return self.is_open and self.impact_level == "CRITICAL"


class ProjectStakeholder(UuidPrimaryKeyMixin, AuditColumnsMixin, VersionMixin, Base):
    __tablename__ = "project_stakeholders"
    __table_args__ = (
        Index(
            "ux_project_stakeholders_project_person_role_active",
            "project_id",
            "key_person_id",
            "role",
            unique=True,
            postgresql_where=text("active = true"),
        ),
        {"schema": "portfolio"},
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolio.projects.id"), nullable=False
    )
    key_person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolio.key_people.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(60), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    project: Mapped[Project] = relationship(back_populates="key_people")
    key_person: Mapped[KeyPerson] = relationship(back_populates="project_stakeholders")


class Resource(UuidPrimaryKeyMixin, AuditColumnsMixin, VersionMixin, Base):
    __tablename__ = "resources"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_resources_name_not_blank"),
        CheckConstraint(
            "default_weekly_capacity >= 0 AND default_weekly_capacity <= 150",
            name="ck_resources_default_weekly_capacity_range",
        ),
        Index("ux_resources_user_id", "user_id", unique=True),
        Index("ix_resources_discipline", "discipline"),
        Index("ix_resources_role_type", "role_type"),
        {"schema": "resource"},
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security.users.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    discipline: Mapped[str] = mapped_column(String(40), nullable=False)
    role_type: Mapped[str] = mapped_column(String(60), nullable=False)
    specialization: Mapped[str | None] = mapped_column(String(120), nullable=True)
    seniority: Mapped[str | None] = mapped_column(String(80), nullable=True)
    default_weekly_capacity: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("100.00"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(40), default="AVAILABLE", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped[User | None] = relationship(back_populates="resource", foreign_keys=[user_id])
    allocations: Mapped[list[Allocation]] = relationship(back_populates="resource")
    availability_overrides: Mapped[list[ResourceAvailability]] = relationship(
        back_populates="resource"
    )
    skills: Mapped[list[ResourceSkill]] = relationship(back_populates="resource")


class KeyPeopleDirectory(UuidPrimaryKeyMixin, AuditColumnsMixin, VersionMixin, Base):
    __tablename__ = "key_people_directory"
    __table_args__ = (
        Index(
            "ux_key_people_directory_role_person",
            "role",
            "key_person_id",
            unique=True,
            postgresql_where=text("active = true"),
        ),
        Index("ix_key_people_directory_role", "role"),
        {"schema": "portfolio"},
    )

    role: Mapped[str] = mapped_column(String(60), nullable=False)
    key_person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolio.key_people.id"), nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    key_person: Mapped[KeyPerson] = relationship(back_populates="directory_assignments")


class KeyPerson(UuidPrimaryKeyMixin, AuditColumnsMixin, VersionMixin, Base):
    __tablename__ = "key_people"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_key_people_name_not_blank"),
        Index("ix_key_people_name", "name"),
        {"schema": "portfolio"},
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    business_area: Mapped[str | None] = mapped_column(String(40), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    project_stakeholders: Mapped[list[ProjectStakeholder]] = relationship(
        back_populates="key_person"
    )
    directory_assignments: Mapped[list[KeyPeopleDirectory]] = relationship(
        back_populates="key_person"
    )


class CalendarWeek(UuidPrimaryKeyMixin, Base):
    __tablename__ = "calendar_weeks"
    __table_args__ = (
        CheckConstraint("iso_week >= 1 AND iso_week <= 53", name="ck_calendar_weeks_iso_week"),
        CheckConstraint("end_date >= start_date", name="ck_calendar_weeks_end_after_start"),
        Index("ux_calendar_weeks_iso_year_week", "iso_year", "iso_week", unique=True),
        {"schema": "capacity"},
    )

    iso_year: Mapped[int] = mapped_column(nullable=False)
    iso_week: Mapped[int] = mapped_column(nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    allocations: Mapped[list[Allocation]] = relationship(back_populates="calendar_week")
    availability_overrides: Mapped[list[ResourceAvailability]] = relationship(
        back_populates="calendar_week"
    )


class ResourceAvailability(UuidPrimaryKeyMixin, AuditColumnsMixin, VersionMixin, Base):
    __tablename__ = "resource_availability"
    __table_args__ = (
        CheckConstraint(
            "available_percentage >= 0 AND available_percentage <= 150",
            name="ck_resource_availability_percentage_range",
        ),
        Index(
            "ux_resource_availability_resource_week",
            "resource_id",
            "calendar_week_id",
            unique=True,
        ),
        {"schema": "resource"},
    )

    resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resource.resources.id"), nullable=False
    )
    calendar_week_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("capacity.calendar_weeks.id"), nullable=False
    )
    available_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    resource: Mapped[Resource] = relationship(back_populates="availability_overrides")
    calendar_week: Mapped[CalendarWeek] = relationship(back_populates="availability_overrides")


class Allocation(UuidPrimaryKeyMixin, AuditColumnsMixin, VersionMixin, Base):
    __tablename__ = "allocations"
    __table_args__ = (
        CheckConstraint(
            "percentage > 0 AND percentage <= 150",
            name="ck_allocations_percentage_range",
        ),
        CheckConstraint(
            "allocation_type <> 'PROJECT' OR project_id IS NOT NULL",
            name="ck_allocations_project_required_for_project_type",
        ),
        Index("ix_allocations_resource_week", "resource_id", "calendar_week_id"),
        Index("ix_allocations_project_week", "project_id", "calendar_week_id"),
        {"schema": "capacity"},
    )

    resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resource.resources.id"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolio.projects.id"), nullable=True
    )
    calendar_week_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("capacity.calendar_weeks.id"), nullable=False
    )
    allocation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    resource: Mapped[Resource] = relationship(back_populates="allocations")
    project: Mapped[Project | None] = relationship(back_populates="allocations")
    calendar_week: Mapped[CalendarWeek] = relationship(back_populates="allocations")


class AuditEvent(UuidPrimaryKeyMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_entity", "entity_type", "entity_id", "occurred_at"),
        Index("ix_audit_events_actor", "actor_user_id", "occurred_at"),
        Index("ix_audit_events_correlation_id", "correlation_id"),
        {"schema": "audit"},
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security.users.id"), nullable=True
    )
    actor_display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    old_values: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    new_values: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    request_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    event_metadata: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
