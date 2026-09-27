from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.schemas.capacity import (
    AllocationCreate,
    AllocationUpdate,
    AllocationRangeCreate,
    AllocationRangeUpdate,
    CalendarExtendRequest,
    CalendarWeekCreate,
    KeyPersonCreate,
    KeyPersonUpdate,
    KeyPeopleUpdate,
    ProjectCreate,
    ProjectUpdate,
    ProjectDependencyCreate,
    ProjectDependencyUpdate,
    ResourceCreate,
    ResourceUpdate,
)
from app.application.audit_service import record_audit
from app.core.concurrency import require_version
from app.domain.enums import AllocationType, DependencyStatus
from app.domain.models import (
    Allocation,
    CalendarWeek,
    KeyPeopleDirectory,
    KeyPerson,
    Project,
    ProjectDependency,
    ProjectStakeholder,
    Resource,
    normalize_code,
)


ALLOWED_DEPENDENCY_TRANSITIONS: dict[str, set[str]] = {
    DependencyStatus.OPEN.value: {
        DependencyStatus.IN_PROGRESS.value,
        DependencyStatus.BLOCKED.value,
        DependencyStatus.RESOLVED.value,
        DependencyStatus.CANCELLED.value,
    },
    DependencyStatus.IN_PROGRESS.value: {
        DependencyStatus.OPEN.value,
        DependencyStatus.BLOCKED.value,
        DependencyStatus.RESOLVED.value,
        DependencyStatus.CANCELLED.value,
    },
    DependencyStatus.BLOCKED.value: {
        DependencyStatus.OPEN.value,
        DependencyStatus.IN_PROGRESS.value,
        DependencyStatus.RESOLVED.value,
        DependencyStatus.CANCELLED.value,
    },
    DependencyStatus.RESOLVED.value: {
        DependencyStatus.OPEN.value,
        DependencyStatus.IN_PROGRESS.value,
    },
    DependencyStatus.CANCELLED.value: {DependencyStatus.OPEN.value},
}


async def create_project(session: AsyncSession, payload: ProjectCreate) -> Project:
    project = Project(
        code=payload.code.strip(),
        code_normalized=normalize_code(payload.code),
        name=payload.name.strip(),
        description=payload.description,
        business_area=payload.business_area.value,
        project_type=payload.project_type.value,
        lifecycle_state=payload.lifecycle_state.value,
        priority=payload.priority.value,
        delivery_model=payload.delivery_model.value,
        edpx_card_url=payload.edpx_card_url,
        jira_url=payload.jira_url,
        confluence_url=payload.confluence_url,
        figma_url=payload.figma_url,
        start_date=payload.start_date,
        target_end_date=payload.target_end_date,
    )
    session.add(project)
    await session.flush()
    await record_audit(session, entity_type="Project", entity_id=project.id, action="CREATE", new_values={"code": project.code, "name": project.name})
    await commit_or_conflict(session, "Project already exists or violates constraints.")
    await session.refresh(project)
    return project


async def list_projects(session: AsyncSession) -> list[Project]:
    result = await session.scalars(
        select(Project)
        .options(selectinload(Project.dependencies))
        .where(Project.active.is_(True))
        .order_by(Project.code)
    )
    return list(result.all())


async def update_project(
    session: AsyncSession, project_id: UUID, payload: ProjectUpdate, expected_version: int
) -> Project:
    project = await session.get(Project, project_id, with_for_update=True)
    if project is None or not project.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    require_version(project.version, expected_version)
    values = payload.model_dump(exclude_unset=True, exclude={"version"})
    old_values = {field: getattr(project, field) for field in values}
    for field, value in values.items():
        setattr(project, field, value.value if hasattr(value, "value") else (value.strip() or None if isinstance(value, str) and field in {"description", "edpx_card_url", "jira_url", "confluence_url", "figma_url"} else value))
    project.version += 1
    await record_audit(session, entity_type="Project", entity_id=project.id, action="UPDATE", old_values=old_values, new_values={field: getattr(project, field) for field in values})
    await commit_or_conflict(session, "Project update violates constraints.")
    await session.refresh(project)
    return project


def is_blocking_dependency(dependency: ProjectDependency) -> bool:
    return dependency.status == DependencyStatus.BLOCKED.value or (
        dependency.status in {
            DependencyStatus.OPEN.value,
            DependencyStatus.IN_PROGRESS.value,
            DependencyStatus.BLOCKED.value,
        }
        and dependency.impact_level == "CRITICAL"
    )


async def list_project_dependencies(
    session: AsyncSession, project_id: UUID
) -> list[ProjectDependency]:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return await scalars_list(
        session,
        select(ProjectDependency)
        .options(selectinload(ProjectDependency.owner))
        .where(ProjectDependency.project_id == project_id)
        .order_by(ProjectDependency.target_date, ProjectDependency.title),
    )


async def list_dependencies(session: AsyncSession) -> list[ProjectDependency]:
    return await scalars_list(
        session,
        select(ProjectDependency).options(selectinload(ProjectDependency.owner)).order_by(
            ProjectDependency.status, ProjectDependency.target_date, ProjectDependency.title
        ),
    )


async def list_project_stakeholders(
    session: AsyncSession, project_id: UUID
) -> list[ProjectStakeholder]:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    result = await session.scalars(
        select(ProjectStakeholder)
        .options(selectinload(ProjectStakeholder.key_person))
        .where(ProjectStakeholder.project_id == project_id, ProjectStakeholder.active.is_(True))
        .order_by(ProjectStakeholder.role)
    )
    return list(result.all())


async def list_key_people_directory(session: AsyncSession) -> list[KeyPeopleDirectory]:
    result = await session.scalars(
        select(KeyPeopleDirectory)
        .options(selectinload(KeyPeopleDirectory.key_person))
        .where(KeyPeopleDirectory.active.is_(True))
        .order_by(KeyPeopleDirectory.role, KeyPeopleDirectory.key_person_id)
    )
    return list(result.all())


async def replace_key_people_directory(
    session: AsyncSession, payload: KeyPeopleUpdate
) -> list[KeyPeopleDirectory]:
    pairs = [(assignment.role.value, assignment.key_person_id) for assignment in payload.assignments]
    if len(pairs) != len(set(pairs)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Each person can only be assigned once per key people role.",
        )
    key_person_ids = {key_person_id for _, key_person_id in pairs}
    key_people = list(
        (
            await session.scalars(
                select(KeyPerson).where(KeyPerson.id.in_(key_person_ids), KeyPerson.active.is_(True))
            )
        ).all()
    )
    if len(key_people) != len(key_person_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="One or more selected people are no longer active.",
        )

    current = list(
        (
            await session.scalars(
                select(KeyPeopleDirectory)
            )
        ).all()
    )
    active_pairs = set(pairs)
    for entry in current:
        should_be_active = (entry.role, entry.key_person_id) in active_pairs
        if entry.active != should_be_active:
            entry.active = should_be_active
            entry.version += 1

    existing_pairs = {(entry.role, entry.key_person_id) for entry in current}
    session.add_all(
        [
            KeyPeopleDirectory(role=role, key_person_id=key_person_id)
            for role, key_person_id in pairs
            if (role, key_person_id) not in existing_pairs
        ]
    )
    await record_audit(session, entity_type="KeyPeopleDirectory", entity_id=key_people[0].id if key_people else UUID(int=0), action="REPLACE", new_values={"assignments": len(pairs)})
    await commit_or_conflict(session, "Key people directory update violates constraints.")
    result = await session.scalars(
        select(KeyPeopleDirectory)
        .options(selectinload(KeyPeopleDirectory.key_person))
        .where(KeyPeopleDirectory.active.is_(True))
        .order_by(KeyPeopleDirectory.role, KeyPeopleDirectory.key_person_id)
    )
    return list(result.all())


async def replace_project_stakeholders(
    session: AsyncSession, project_id: UUID, assignments: list[tuple[str, UUID]]
) -> list[ProjectStakeholder]:
    project = await session.get(Project, project_id, with_for_update=True)
    if project is None or not project.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    key_person_ids = {key_person_id for _, key_person_id in assignments}
    key_people = list(
        (
            await session.scalars(
                select(KeyPerson).where(KeyPerson.id.in_(key_person_ids), KeyPerson.active.is_(True))
            )
        ).all()
    )
    if len(key_people) != len(key_person_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="One or more selected people are no longer active.",
        )

    current = list(
        (
            await session.scalars(
                select(ProjectStakeholder).where(
                    ProjectStakeholder.project_id == project_id,
                    ProjectStakeholder.active.is_(True),
                )
            )
        ).all()
    )
    for stakeholder in current:
        stakeholder.active = False
        stakeholder.version += 1

    stakeholders = [
        ProjectStakeholder(project_id=project_id, key_person_id=key_person_id, role=role)
        for role, key_person_id in assignments
    ]
    session.add_all(stakeholders)
    await record_audit(session, entity_type="ProjectStakeholder", entity_id=project_id, action="REPLACE", new_values={"assignments": len(assignments)})
    await commit_or_conflict(session, "Project key people update violates constraints.")
    result = await session.scalars(
        select(ProjectStakeholder)
        .options(selectinload(ProjectStakeholder.key_person))
        .where(ProjectStakeholder.project_id == project_id, ProjectStakeholder.active.is_(True))
        .order_by(ProjectStakeholder.role)
    )
    return list(result.all())


async def list_key_people(session: AsyncSession) -> list[KeyPerson]:
    return await scalars_list(session, select(KeyPerson).where(KeyPerson.active.is_(True)).order_by(KeyPerson.name))


async def create_key_person(session: AsyncSession, payload: KeyPersonCreate) -> KeyPerson:
    person = KeyPerson(name=payload.name.strip(), email=payload.email.strip() if payload.email else None, company=payload.company.strip() or "EDP", business_area=payload.business_area.value)
    session.add(person)
    await record_audit(session, entity_type="KeyPerson", entity_id=person.id, action="CREATE", new_values={"name": person.name, "email": person.email})
    await commit_or_conflict(session, "Key person already exists or violates constraints.")
    await session.refresh(person)
    return person


async def update_key_person(
    session: AsyncSession, key_person_id: UUID, payload: KeyPersonUpdate, expected_version: int
) -> KeyPerson:
    person = await session.get(KeyPerson, key_person_id, with_for_update=True)
    if person is None or not person.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key person not found.")
    require_version(person.version, expected_version)
    values = payload.model_dump(exclude_unset=True, exclude={"version"})
    old_values = {field: getattr(person, field) for field in values}
    for field, value in values.items():
        if hasattr(value, "value"):
            value = value.value
        elif isinstance(value, str) and field in {"name", "company", "email"}:
            value = value.strip() or None
        if field == "name" and value is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Key person name cannot be blank.")
        setattr(person, field, value)
    person.version += 1
    await record_audit(session, entity_type="KeyPerson", entity_id=person.id, action="UPDATE", old_values=old_values, new_values={field: getattr(person, field) for field in values})
    await commit_or_conflict(session, "Key person update violates constraints.")
    await session.refresh(person)
    return person


async def deactivate_key_person(session: AsyncSession, key_person_id: UUID) -> KeyPerson:
    person = await session.get(KeyPerson, key_person_id, with_for_update=True)
    if person is None or not person.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key person not found.")
    person.active = False
    person.version += 1
    entries = await session.scalars(select(KeyPeopleDirectory).where(KeyPeopleDirectory.key_person_id == key_person_id, KeyPeopleDirectory.active.is_(True)))
    for entry in entries:
        entry.active = False
        entry.version += 1
    await record_audit(session, entity_type="KeyPerson", entity_id=person.id, action="DEACTIVATE", old_values={"active": True}, new_values={"active": False})
    await commit_or_conflict(session, "Key person update violates constraints.")
    return person


async def create_project_dependency(
    session: AsyncSession, project_id: UUID, payload: ProjectDependencyCreate
) -> ProjectDependency:
    project = await session.get(Project, project_id)
    if project is None or not project.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    if payload.target_date < payload.start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="target_date must be on or after start_date.",
        )
    if payload.status in {DependencyStatus.RESOLVED, DependencyStatus.CANCELLED}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A new dependency must start as OPEN, IN_PROGRESS or BLOCKED.",
        )
    if payload.owner_key_person_id is not None:
        owner = await session.get(KeyPerson, payload.owner_key_person_id)
        if owner is None or not owner.active:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Dependency owner is not active.")

    dependency = ProjectDependency(
        project_id=project_id,
        owner_key_person_id=payload.owner_key_person_id,
        dependency_type=payload.dependency_type.value,
        title=payload.title.strip(),
        title_normalized=normalize_code(payload.title),
        description=payload.description.strip(),
        status=payload.status.value,
        start_date=payload.start_date,
        target_date=payload.target_date,
        resolved_date=None,
        cancellation_reason=None,
        impact_level=payload.impact_level.value,
        mitigation_plan=payload.mitigation_plan,
        external_reference=payload.external_reference,
    )
    session.add(dependency)
    await session.flush()
    await record_audit(
        session,
        entity_type="ProjectDependency",
        entity_id=dependency.id,
        action="CREATE",
        new_values={"title": dependency.title, "status": dependency.status},
    )
    await commit_or_conflict(session, "Dependency already exists or violates constraints.")
    await session.refresh(dependency)
    return dependency


async def update_project_dependency(
    session: AsyncSession,
    dependency_id: UUID,
    payload: ProjectDependencyUpdate,
    project_id: UUID | None = None,
    expected_version: int | None = None,
) -> ProjectDependency:
    dependency = await session.get(ProjectDependency, dependency_id, with_for_update=True)
    if dependency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency not found.")
    if project_id is not None and dependency.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency not found.")
    require_version(dependency.version, expected_version if expected_version is not None else payload.version or -1)

    values = payload.model_dump(exclude_unset=True, exclude={"version"})
    old_values = {
        "status": dependency.status,
        "owner_key_person_id": str(dependency.owner_key_person_id) if dependency.owner_key_person_id else None,
        "start_date": dependency.start_date.isoformat(),
        "target_date": dependency.target_date.isoformat(),
        "resolved_date": dependency.resolved_date.isoformat() if dependency.resolved_date else None,
        "impact_level": dependency.impact_level,
        "cancellation_reason": dependency.cancellation_reason,
    }
    if "owner_key_person_id" in values and values["owner_key_person_id"] is not None:
        owner = await session.get(KeyPerson, values["owner_key_person_id"])
        if owner is None or not owner.active:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Dependency owner is not active.")
    for field in ("dependency_type", "status", "impact_level"):
        if field in values and values[field] is not None:
            values[field] = values[field].value
    if "title" in values and values["title"] is not None:
        values["title"] = values["title"].strip()
        values["title_normalized"] = normalize_code(values["title"])
    if "description" in values and values["description"] is not None:
        values["description"] = values["description"].strip()

    requested_status = values.get("status", dependency.status)
    if requested_status != dependency.status and requested_status not in ALLOWED_DEPENDENCY_TRANSITIONS.get(dependency.status, set()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid dependency status transition: {dependency.status} -> {requested_status}.",
        )

    start_date = values.get("start_date", dependency.start_date)
    target_date = values.get("target_date", dependency.target_date)
    if target_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="target_date must be on or after start_date.",
        )

    resolved_date = values.get("resolved_date", dependency.resolved_date)
    cancellation_reason = values.get("cancellation_reason", dependency.cancellation_reason)
    if requested_status == DependencyStatus.RESOLVED.value:
        if resolved_date is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="resolved_date is required when a dependency is RESOLVED.",
            )
        if resolved_date < start_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="resolved_date must be on or after start_date.",
            )
        cancellation_reason = None
    elif requested_status == DependencyStatus.CANCELLED.value:
        cancellation_reason = (cancellation_reason or "").strip()
        if not cancellation_reason:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="cancellation_reason is required when a dependency is CANCELLED.",
            )
        resolved_date = None
    else:
        resolved_date = None
        cancellation_reason = None

    values["resolved_date"] = resolved_date
    values["cancellation_reason"] = cancellation_reason
    for field, value in values.items():
        setattr(dependency, field, value)
    dependency.version += 1
    await record_audit(
        session,
        entity_type="ProjectDependency",
        entity_id=dependency.id,
        action="UPDATE",
        old_values=old_values,
        new_values={
            "status": dependency.status,
            "owner_key_person_id": str(dependency.owner_key_person_id) if dependency.owner_key_person_id else None,
            "start_date": dependency.start_date.isoformat(),
            "target_date": dependency.target_date.isoformat(),
            "resolved_date": dependency.resolved_date.isoformat() if dependency.resolved_date else None,
            "impact_level": dependency.impact_level,
            "cancellation_reason": dependency.cancellation_reason,
        },
    )
    await commit_or_conflict(session, "Dependency update violates constraints.")
    await session.refresh(dependency)
    return dependency


async def delete_project_dependency(
    session: AsyncSession, dependency_id: UUID, project_id: UUID | None = None, expected_version: int | None = None
) -> None:
    dependency = await session.get(ProjectDependency, dependency_id, with_for_update=True)
    if dependency is None or (project_id is not None and dependency.project_id != project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency not found.")
    require_version(dependency.version, expected_version if expected_version is not None else -1)
    if dependency.status == DependencyStatus.CANCELLED.value:
        return
    old_status = dependency.status
    dependency.status = DependencyStatus.CANCELLED.value
    dependency.resolved_date = None
    dependency.cancellation_reason = "Cancelada pelo utilizador."
    dependency.version += 1
    await record_audit(
        session,
        entity_type="ProjectDependency",
        entity_id=dependency.id,
        action="CANCEL",
        old_values={"status": old_status},
        new_values={"status": dependency.status, "cancellation_reason": dependency.cancellation_reason},
    )
    await commit_or_conflict(session, "Dependency could not be cancelled.")


async def deactivate_project(session: AsyncSession, project_id: UUID, expected_version: int | None = None) -> Project:
    project = await session.get(Project, project_id, with_for_update=True)
    if project is None or not project.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    if expected_version is not None:
        require_version(project.version, expected_version)

    project.active = False
    project.version += 1
    await record_audit(session, entity_type="Project", entity_id=project.id, action="DEACTIVATE", old_values={"active": True}, new_values={"active": False})
    await commit_or_conflict(session, "Project deactivation violates constraints.")
    await session.refresh(project)
    return project


async def create_resource(session: AsyncSession, payload: ResourceCreate) -> Resource:
    resource = Resource(
        name=payload.name.strip(),
        company=payload.company.strip() or "EDP",
        email=payload.email,
        discipline=payload.discipline.value,
        role_type=payload.role_type.value,
        specialization=payload.specialization,
        seniority=payload.seniority,
        default_weekly_capacity=payload.default_weekly_capacity,
        status=payload.status.value,
    )
    session.add(resource)
    await record_audit(session, entity_type="Resource", entity_id=resource.id, action="CREATE", new_values={"name": resource.name, "discipline": resource.discipline})
    await commit_or_conflict(session, "Resource already exists or violates constraints.")
    await session.refresh(resource)
    return resource


async def list_resources(session: AsyncSession) -> list[Resource]:
    return await scalars_list(session, select(Resource).order_by(Resource.name))


async def update_resource(
    session: AsyncSession, resource_id: UUID, payload: ResourceUpdate, expected_version: int
) -> Resource:
    resource = await session.get(Resource, resource_id, with_for_update=True)
    if resource is None or not resource.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found.")
    require_version(resource.version, expected_version)
    values = payload.model_dump(exclude_unset=True, exclude={"version"})
    old_values = {
        field: str(getattr(resource, field)) if isinstance(getattr(resource, field), Decimal) else getattr(resource, field)
        for field in values
    }
    for field, value in values.items():
        if hasattr(value, "value"):
            value = value.value
        elif isinstance(value, str) and field in {"name", "company", "email", "specialization", "seniority"}:
            value = value.strip() or None
        if field == "name" and value is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Resource name cannot be blank.")
        setattr(resource, field, value)
    resource.version += 1
    await record_audit(
        session,
        entity_type="Resource",
        entity_id=resource.id,
        action="UPDATE",
        old_values=old_values,
        new_values={
            field: str(getattr(resource, field)) if isinstance(getattr(resource, field), Decimal) else getattr(resource, field)
            for field in values
        },
    )
    await commit_or_conflict(session, "Resource update violates constraints.")
    await session.refresh(resource)
    return resource


async def create_calendar_week(session: AsyncSession, payload: CalendarWeekCreate) -> CalendarWeek:
    if payload.end_date < payload.start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be on or after start_date.",
        )

    week = CalendarWeek(
        iso_year=payload.iso_year,
        iso_week=payload.iso_week,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    session.add(week)
    await record_audit(session, entity_type="CalendarWeek", entity_id=week.id, action="CREATE", new_values={"iso_year": week.iso_year, "iso_week": week.iso_week})
    await commit_or_conflict(session, "Calendar week already exists or violates constraints.")
    await session.refresh(week)
    return week


async def list_calendar_weeks(session: AsyncSession) -> list[CalendarWeek]:
    return await scalars_list(
        session, select(CalendarWeek).order_by(CalendarWeek.iso_year, CalendarWeek.iso_week)
    )


async def extend_calendar_weeks(
    session: AsyncSession,
    payload: CalendarExtendRequest,
) -> tuple[int, int]:
    if payload.until_year is None and payload.weeks_ahead is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="until_year or weeks_ahead is required.",
        )

    existing_result = await session.execute(
        select(CalendarWeek.iso_year, CalendarWeek.iso_week, CalendarWeek.end_date)
    )
    existing_rows = list(existing_result)
    existing_keys = {(row.iso_year, row.iso_week) for row in existing_rows}
    latest_end_date = max((row.end_date for row in existing_rows), default=None)
    start_date = latest_end_date + timedelta(days=1) if latest_end_date else None
    candidates = calendar_week_candidates(payload, start_date=start_date)
    created = 0

    for iso_year, iso_week, start_date, end_date in candidates:
        if (iso_year, iso_week) in existing_keys:
            continue
        session.add(
            CalendarWeek(
                iso_year=iso_year,
                iso_week=iso_week,
                start_date=start_date,
                end_date=end_date,
            )
        )
        existing_keys.add((iso_year, iso_week))
        created += 1

    await commit_or_conflict(session, "Calendar extension violates constraints.")
    total = await session.scalar(select(func.count()).select_from(CalendarWeek))
    return created, int(total or 0)


def calendar_week_candidates(
    payload: CalendarExtendRequest,
    *,
    start_date: date | None = None,
) -> list[tuple[int, int, date, date]]:
    if start_date:
        first_date = start_date
        current_monday = first_date + timedelta(days=(7 - first_date.weekday()) % 7)
    else:
        today = datetime.now(UTC).date()
        current_monday = today - timedelta(days=today.weekday())

    if payload.weeks_ahead is not None:
        end_monday = current_monday + timedelta(weeks=payload.weeks_ahead - 1)
    else:
        assert payload.until_year is not None
        end_monday = date.fromisocalendar(payload.until_year, last_iso_week(payload.until_year), 1)

    candidates: list[tuple[int, int, date, date]] = []
    cursor = current_monday
    while cursor <= end_monday:
        iso_year, iso_week, _ = cursor.isocalendar()
        candidates.append((iso_year, iso_week, cursor, cursor + timedelta(days=6)))
        cursor += timedelta(weeks=1)
    return candidates


def last_iso_week(year: int) -> int:
    return date(year, 12, 28).isocalendar().week


async def create_allocation(session: AsyncSession, payload: AllocationCreate) -> Allocation:
    if payload.allocation_type == AllocationType.PROJECT and payload.project_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="project_id is required for PROJECT allocations.",
        )

    resource = await session.get(Resource, payload.resource_id, with_for_update=True)
    if resource is None or not resource.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found.")

    week = await session.get(CalendarWeek, payload.calendar_week_id)
    if week is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Calendar week not found."
        )

    if payload.project_id is not None:
        project = await session.get(Project, payload.project_id)
        if project is None or not project.active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    allocated = await current_allocated_percentage(
        session,
        resource_id=payload.resource_id,
        calendar_week_id=payload.calendar_week_id,
    )
    if allocated + payload.percentage > Decimal("150.00"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Resource allocation for the week cannot exceed 150%.",
        )

    allocation = Allocation(
        resource_id=payload.resource_id,
        project_id=payload.project_id,
        calendar_week_id=payload.calendar_week_id,
        allocation_type=payload.allocation_type.value,
        percentage=payload.percentage,
        notes=payload.notes,
    )
    session.add(allocation)
    await record_audit(session, entity_type="Allocation", entity_id=allocation.id, action="CREATE", new_values={"resource_id": str(allocation.resource_id), "calendar_week_id": str(allocation.calendar_week_id), "percentage": str(allocation.percentage)})
    await commit_or_conflict(session, "Allocation violates constraints.")
    await session.refresh(allocation)
    return allocation


async def create_allocation_range(
    session: AsyncSession, payload: AllocationRangeCreate
) -> list[Allocation]:
    if payload.allocation_type == AllocationType.PROJECT and payload.project_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="project_id is required for PROJECT allocations.",
        )

    resource = await session.get(Resource, payload.resource_id, with_for_update=True)
    if resource is None or not resource.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found.")
    if payload.project_id is not None:
        project = await session.get(Project, payload.project_id)
        if project is None or not project.active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    start_week = await session.get(CalendarWeek, payload.start_week_id)
    end_week = await session.get(CalendarWeek, payload.end_week_id)
    if start_week is None or end_week is None or start_week.start_date > end_week.start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The selected week range is invalid.",
        )

    weeks = list(
        (
            await session.scalars(
                select(CalendarWeek)
                .where(
                    CalendarWeek.start_date >= start_week.start_date,
                    CalendarWeek.end_date <= end_week.end_date,
                )
                .order_by(CalendarWeek.start_date)
            )
        ).all()
    )
    if not weeks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The selected week range is invalid.",
        )

    created: list[Allocation] = []
    for week in weeks:
        allocated = await current_allocated_percentage(
            session,
            resource_id=payload.resource_id,
            calendar_week_id=week.id,
        )
        if allocated + payload.percentage > Decimal("150.00"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Resource allocation for {week.iso_year}-W{week.iso_week} "
                    "cannot exceed 150%."
                ),
            )
        allocation = Allocation(
            resource_id=payload.resource_id,
            project_id=payload.project_id,
            calendar_week_id=week.id,
            allocation_type=payload.allocation_type.value,
            percentage=payload.percentage,
            notes=payload.notes,
        )
        session.add(allocation)
        created.append(allocation)

    await record_audit(session, entity_type="Allocation", entity_id=payload.resource_id, action="CREATE_RANGE", new_values={"created": len(created), "start_week_id": str(payload.start_week_id), "end_week_id": str(payload.end_week_id)})
    await commit_or_conflict(session, "Allocation range violates constraints.")
    for allocation in created:
        await session.refresh(allocation)
    return created


async def update_allocation_range(
    session: AsyncSession, payload: AllocationRangeUpdate
) -> tuple[int, int]:
    allocations = list(
        (
            await session.scalars(
                select(Allocation)
                .where(Allocation.id.in_(payload.allocation_ids))
                .with_for_update()
            )
        ).all()
    )
    if len(allocations) != len(set(payload.allocation_ids)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation not found.")

    first = allocations[0]
    if any(
        allocation.resource_id != first.resource_id
        or allocation.project_id != first.project_id
        or allocation.allocation_type != first.allocation_type
        or allocation.percentage != first.percentage
        or allocation.notes != first.notes
        for allocation in allocations
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selected allocations do not belong to one editable group.",
        )

    start_week = await session.get(CalendarWeek, payload.start_week_id)
    end_week = await session.get(CalendarWeek, payload.end_week_id)
    if start_week is None or end_week is None or start_week.start_date > end_week.start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The selected week range is invalid.",
        )

    weeks = list(
        (
            await session.scalars(
                select(CalendarWeek)
                .where(
                    CalendarWeek.start_date >= start_week.start_date,
                    CalendarWeek.end_date <= end_week.end_date,
                )
                .order_by(CalendarWeek.start_date)
            )
        ).all()
    )
    if not weeks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The selected week range is invalid.",
        )

    selected_week_ids = {allocation.calendar_week_id for allocation in allocations}
    target_week_ids = {week.id for week in weeks}
    created = 0
    for week in weeks:
        if week.id in selected_week_ids:
            continue
        allocated = await current_allocated_percentage(
            session,
            resource_id=first.resource_id,
            calendar_week_id=week.id,
        )
        if allocated + first.percentage > Decimal("150.00"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Resource allocation for {week.iso_year}-W{week.iso_week} "
                    "cannot exceed 150%."
                ),
            )
        session.add(
            Allocation(
                resource_id=first.resource_id,
                project_id=first.project_id,
                calendar_week_id=week.id,
                allocation_type=first.allocation_type,
                percentage=first.percentage,
                notes=first.notes,
            )
        )
        created += 1

    deleted = 0
    for allocation in allocations:
        if allocation.calendar_week_id not in target_week_ids:
            await session.delete(allocation)
            deleted += 1

    await record_audit(session, entity_type="Allocation", entity_id=first.id, action="UPDATE_RANGE", new_values={"created": created, "deleted": deleted, "start_week_id": str(payload.start_week_id), "end_week_id": str(payload.end_week_id)})
    await commit_or_conflict(session, "Allocation range update violates constraints.")
    return created, deleted


async def update_allocation(
    session: AsyncSession,
    allocation_id: UUID,
    payload: AllocationUpdate,
    expected_version: int,
) -> Allocation:
    allocation = await session.get(Allocation, allocation_id, with_for_update=True)
    if allocation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation not found.")
    require_version(allocation.version, expected_version)

    values = payload.model_dump(exclude_unset=True, exclude={"version"})
    next_type = values.get("allocation_type", allocation.allocation_type)
    next_type = next_type.value if hasattr(next_type, "value") else next_type
    next_percentage = values.get("percentage", allocation.percentage)

    if next_type == AllocationType.PROJECT.value and allocation.project_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="project_id is required for PROJECT allocations.",
        )

    current_total = await current_allocated_percentage(
        session,
        resource_id=allocation.resource_id,
        calendar_week_id=allocation.calendar_week_id,
    )
    next_total = current_total - allocation.percentage + next_percentage
    if next_total > Decimal("150.00"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Resource allocation for the week cannot exceed 150%.",
        )

    old_values = {
        "allocation_type": allocation.allocation_type,
        "percentage": str(allocation.percentage),
    }
    allocation.allocation_type = next_type
    allocation.percentage = next_percentage
    allocation.version += 1
    await record_audit(
        session,
        entity_type="Allocation",
        entity_id=allocation.id,
        action="UPDATE",
        old_values=old_values,
        new_values={"allocation_type": allocation.allocation_type, "percentage": str(allocation.percentage)},
    )
    await commit_or_conflict(session, "Allocation update violates constraints.")
    await session.refresh(allocation)
    return allocation


async def delete_allocation(
    session: AsyncSession,
    allocation_id: UUID,
    expected_version: int,
) -> None:
    allocation = await session.get(Allocation, allocation_id, with_for_update=True)
    if allocation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation not found.")
    require_version(allocation.version, expected_version)
    await record_audit(
        session,
        entity_type="Allocation",
        entity_id=allocation.id,
        action="DELETE",
        old_values={
            "resource_id": str(allocation.resource_id),
            "calendar_week_id": str(allocation.calendar_week_id),
            "percentage": str(allocation.percentage),
        },
    )
    await session.delete(allocation)
    await commit_or_conflict(session, "Allocation could not be deleted.")


async def list_allocations(session: AsyncSession) -> list[Allocation]:
    return await scalars_list(
        session, select(Allocation).order_by(Allocation.resource_id, Allocation.calendar_week_id)
    )


async def current_allocated_percentage(
    session: AsyncSession,
    *,
    resource_id: UUID,
    calendar_week_id: UUID,
) -> Decimal:
    statement = select(func.coalesce(func.sum(Allocation.percentage), 0)).where(
        Allocation.resource_id == resource_id,
        Allocation.calendar_week_id == calendar_week_id,
    )
    value = await session.scalar(statement)
    return Decimal(str(value or "0"))


async def scalars_list[T](session: AsyncSession, statement: Select[tuple[T]]) -> list[T]:
    result = await session.scalars(statement)
    return list(result.all())


async def commit_or_conflict(session: AsyncSession, detail: str) -> None:
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from error
