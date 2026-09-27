from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    AllocationType,
    BusinessArea,
    DeliveryModel,
    DependencyStatus,
    DependencyType,
    Discipline,
    ImpactLevel,
    LifecycleState,
    Priority,
    ProjectRole,
    ProjectType,
    ResourceRoleType,
    ResourceStatus,
)


class ProjectCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    business_area: BusinessArea
    project_type: ProjectType
    lifecycle_state: LifecycleState = LifecycleState.IDENTIFIED
    priority: Priority = Priority.MEDIUM
    delivery_model: DeliveryModel = DeliveryModel.INTERNAL
    edpx_card_url: str | None = Field(default=None, max_length=2000)
    jira_url: str | None = Field(default=None, max_length=2000)
    confluence_url: str | None = Field(default=None, max_length=2000)
    figma_url: str | None = Field(default=None, max_length=2000)
    start_date: date | None = None
    target_end_date: date | None = None


class ProjectUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=4000)
    business_area: BusinessArea | None = None
    project_type: ProjectType | None = None
    lifecycle_state: LifecycleState | None = None
    priority: Priority | None = None
    delivery_model: DeliveryModel | None = None
    edpx_card_url: str | None = Field(default=None, max_length=2000)
    jira_url: str | None = Field(default=None, max_length=2000)
    confluence_url: str | None = Field(default=None, max_length=2000)
    figma_url: str | None = Field(default=None, max_length=2000)
    version: int | None = None


class PartnerCompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    contact_name: str | None = Field(default=None, max_length=200)
    contact_email: str | None = Field(default=None, max_length=320)
    notes: str | None = Field(default=None, max_length=2000)


class PartnerCompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    contact_name: str | None
    contact_email: str | None
    notes: str | None
    active: bool
    version: int


class ProjectPartnerCreate(BaseModel):
    partner_company_id: UUID
    contribution_description: str | None = Field(default=None, max_length=2000)
    contribution_percentage: Decimal | None = Field(default=None, ge=0, le=100)


class ProjectPartnerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    partner_company_id: UUID
    contribution_description: str | None
    contribution_percentage: Decimal | None


class SprintCreate(BaseModel):
    sprint_number: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=200)
    start_date: date
    end_date: date
    goal: str | None = Field(default=None, max_length=2000)


class SprintRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    sprint_number: int
    name: str
    start_date: date
    end_date: date
    goal: str | None
    version: int


class SkillCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str | None = Field(default=None, max_length=80)


class SkillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    category: str | None
    active: bool
    version: int


class ResourceSkillCreate(BaseModel):
    skill_id: UUID
    level: int = Field(ge=1, le=5)


class ResourceSkillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    resource_id: UUID
    skill_id: UUID
    level: int


class ResourceAvailabilityCreate(BaseModel):
    calendar_week_id: UUID
    available_percentage: Decimal = Field(ge=0, le=150)
    reason: str | None = Field(default=None, max_length=500)


class ResourceAvailabilityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    resource_id: UUID
    calendar_week_id: UUID
    available_percentage: Decimal
    reason: str | None
    version: int


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None
    business_area: BusinessArea
    project_type: ProjectType
    lifecycle_state: LifecycleState
    priority: Priority
    delivery_model: DeliveryModel
    edpx_card_url: str | None
    jira_url: str | None
    confluence_url: str | None
    figma_url: str | None
    start_date: date | None
    target_end_date: date | None
    actual_end_date: date | None
    active: bool
    version: int
    created_at: datetime
    updated_at: datetime
    has_blocking_dependency: bool = False
    blocking_dependency_count: int = 0
    project_at_risk: bool = False


class ProjectDependencyCreate(BaseModel):
    dependency_type: DependencyType
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    status: DependencyStatus = DependencyStatus.OPEN
    start_date: date
    target_date: date
    impact_level: ImpactLevel = ImpactLevel.MEDIUM
    mitigation_plan: str | None = Field(default=None, max_length=2000)
    external_reference: str | None = Field(default=None, max_length=100)
    owner_key_person_id: UUID | None = None


class ProjectDependencyUpdate(BaseModel):
    dependency_type: DependencyType | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    status: DependencyStatus | None = None
    start_date: date | None = None
    target_date: date | None = None
    resolved_date: date | None = None
    impact_level: ImpactLevel | None = None
    mitigation_plan: str | None = Field(default=None, max_length=2000)
    external_reference: str | None = Field(default=None, max_length=100)
    owner_key_person_id: UUID | None = None
    cancellation_reason: str | None = Field(default=None, max_length=2000)
    version: int | None = None


class ProjectDependencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    dependency_type: DependencyType
    title: str
    description: str
    status: DependencyStatus
    start_date: date
    target_date: date
    resolved_date: date | None
    cancellation_reason: str | None
    impact_level: ImpactLevel
    mitigation_plan: str | None
    external_reference: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    owner_key_person_id: UUID | None = None
    is_open: bool = False
    is_overdue: bool = False
    is_critical_open: bool = False
    project_at_risk: bool = False


class ProjectStakeholderAssignment(BaseModel):
    role: ProjectRole
    key_person_id: UUID | None = None


class ProjectStakeholdersUpdate(BaseModel):
    assignments: list[ProjectStakeholderAssignment] = Field(default_factory=list)


class ProjectStakeholderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    key_person_id: UUID
    role: ProjectRole
    active: bool
    person_name: str
    person_email: str | None
    version: int


class KeyPeopleAssignment(BaseModel):
    role: ProjectRole
    key_person_id: UUID


class KeyPeopleUpdate(BaseModel):
    assignments: list[KeyPeopleAssignment] = Field(default_factory=list)


class KeyPeopleDirectoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: ProjectRole
    key_person_id: UUID
    person_name: str
    person_email: str | None
    active: bool
    version: int


class KeyPersonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    company: str = Field(default="EDP", min_length=1, max_length=200)
    business_area: BusinessArea = BusinessArea.BEFS


class KeyPersonUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    company: str | None = Field(default=None, min_length=1, max_length=200)
    business_area: BusinessArea | None = None
    version: int | None = None


class KeyPersonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str | None
    company: str | None
    business_area: BusinessArea | None
    active: bool
    version: int


class ResourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    company: str = Field(default="EDP", min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    discipline: Discipline
    role_type: ResourceRoleType
    specialization: str | None = Field(default=None, max_length=120)
    seniority: str | None = Field(default=None, max_length=80)
    default_weekly_capacity: Decimal = Field(default=Decimal("100.00"), ge=0, le=150)
    status: ResourceStatus = ResourceStatus.AVAILABLE


class ResourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    company: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    discipline: Discipline | None = None
    role_type: ResourceRoleType | None = None
    specialization: str | None = Field(default=None, max_length=120)
    seniority: str | None = Field(default=None, max_length=80)
    default_weekly_capacity: Decimal | None = Field(default=None, ge=0, le=150)
    status: ResourceStatus | None = None
    version: int | None = None


class ResourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None
    name: str
    company: str | None
    email: str | None
    discipline: Discipline
    role_type: ResourceRoleType
    specialization: str | None
    seniority: str | None
    default_weekly_capacity: Decimal
    status: ResourceStatus
    active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class CalendarWeekCreate(BaseModel):
    iso_year: int = Field(ge=2000, le=2100)
    iso_week: int = Field(ge=1, le=53)
    start_date: date
    end_date: date


class CalendarExtendRequest(BaseModel):
    until_year: int | None = Field(default=None, ge=2000, le=2100)
    weeks_ahead: int | None = Field(default=None, ge=1, le=520)


class CalendarExtendResponse(BaseModel):
    created: int
    total_weeks: int


class CalendarWeekRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    iso_year: int
    iso_week: int
    start_date: date
    end_date: date


class AllocationCreate(BaseModel):
    resource_id: UUID
    project_id: UUID | None = None
    calendar_week_id: UUID
    allocation_type: AllocationType = AllocationType.PROJECT
    percentage: Decimal = Field(gt=0, le=150)
    notes: str | None = Field(default=None, max_length=1000)


class AllocationRangeCreate(BaseModel):
    resource_id: UUID
    project_id: UUID | None = None
    allocation_type: AllocationType = AllocationType.PROJECT
    percentage: Decimal = Field(gt=0, le=150)
    notes: str | None = Field(default=None, max_length=1000)
    start_week_id: UUID
    end_week_id: UUID


class AllocationRangeUpdate(BaseModel):
    allocation_ids: list[UUID] = Field(min_length=1)
    start_week_id: UUID
    end_week_id: UUID


class AllocationUpdate(BaseModel):
    allocation_type: AllocationType | None = None
    percentage: Decimal | None = Field(default=None, gt=0, le=150)
    version: int | None = None


class AllocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    resource_id: UUID
    project_id: UUID | None
    calendar_week_id: UUID
    allocation_type: AllocationType
    percentage: Decimal
    notes: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class AllocationRangeRead(BaseModel):
    created: int
    allocations: list[AllocationRead]


class AllocationRangeUpdateRead(BaseModel):
    created: int
    deleted: int
