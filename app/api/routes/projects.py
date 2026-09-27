from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.capacity import (
    ProjectCreate,
    ProjectUpdate,
    ProjectDependencyCreate,
    ProjectDependencyRead,
    ProjectDependencyUpdate,
    ProjectRead,
    ProjectStakeholderRead,
    ProjectStakeholdersUpdate,
)
from app.application.capacity_service import (
    create_project,
    create_project_dependency,
    delete_project_dependency,
    deactivate_project,
    is_blocking_dependency,
    list_dependencies,
    list_project_dependencies,
    list_project_stakeholders,
    list_projects,
    replace_project_stakeholders,
    update_project_dependency,
    update_project,
)
from app.application.import_service import commit_projects, parse_projects, preview_projects
from app.core.database import get_db_session
from app.core.concurrency import etag_for, version_from_if_match
from app.domain.models import ProjectStakeholder

router = APIRouter(prefix="/projects", tags=["projects"])
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
CsvFile = Annotated[UploadFile, File(...)]


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project_endpoint(
    payload: ProjectCreate,
    session: SessionDependency,
) -> ProjectRead:
    project = await create_project(session, payload)
    return ProjectRead.model_validate(project)


@router.get("", response_model=list[ProjectRead])
async def list_projects_endpoint(session: SessionDependency) -> list[ProjectRead]:
    projects = await list_projects(session)
    return [
        ProjectRead.model_validate(project).model_copy(
            update={
                "has_blocking_dependency": any(
                    is_blocking_dependency(dependency) for dependency in project.dependencies
                ),
                "blocking_dependency_count": sum(
                    is_blocking_dependency(dependency) for dependency in project.dependencies
                ),
                "project_at_risk": any(
                    dependency.is_critical_open for dependency in project.dependencies
                ),
            }
        )
        for project in projects
    ]


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project_endpoint(
    project_id: UUID,
    payload: ProjectUpdate,
    session: SessionDependency,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> ProjectRead:
    project = await update_project(session, project_id, payload, version_from_if_match(if_match))
    response.headers["ETag"] = etag_for(project.version)
    return ProjectRead.model_validate(project)


@router.get("/dependencies", response_model=list[ProjectDependencyRead])
async def list_dependencies_endpoint(session: SessionDependency) -> list[ProjectDependencyRead]:
    dependencies = await list_dependencies(session)
    return [ProjectDependencyRead.model_validate(dependency) for dependency in dependencies]


def stakeholder_read(stakeholder: ProjectStakeholder) -> ProjectStakeholderRead:
    return ProjectStakeholderRead(
        id=stakeholder.id,
        project_id=stakeholder.project_id,
        key_person_id=stakeholder.key_person_id,
        role=stakeholder.role,
        active=stakeholder.active,
        person_name=stakeholder.key_person.name,
        person_email=stakeholder.key_person.email,
        version=stakeholder.version,
    )


@router.get("/{project_id}/stakeholders", response_model=list[ProjectStakeholderRead])
async def list_project_stakeholders_endpoint(
    project_id: UUID, session: SessionDependency
) -> list[ProjectStakeholderRead]:
    stakeholders = await list_project_stakeholders(session, project_id)
    return [stakeholder_read(stakeholder) for stakeholder in stakeholders]


@router.put("/{project_id}/stakeholders", response_model=list[ProjectStakeholderRead])
async def replace_project_stakeholders_endpoint(
    project_id: UUID,
    payload: ProjectStakeholdersUpdate,
    session: SessionDependency,
) -> list[ProjectStakeholderRead]:
    assignments = [
        (assignment.role.value, assignment.key_person_id)
        for assignment in payload.assignments
        if assignment.key_person_id is not None
    ]
    stakeholders = await replace_project_stakeholders(session, project_id, assignments)
    return [stakeholder_read(stakeholder) for stakeholder in stakeholders]


@router.get("/{project_id}/dependencies", response_model=list[ProjectDependencyRead])
async def list_project_dependencies_endpoint(
    project_id: UUID, session: SessionDependency
) -> list[ProjectDependencyRead]:
    dependencies = await list_project_dependencies(session, project_id)
    return [ProjectDependencyRead.model_validate(dependency) for dependency in dependencies]


@router.post(
    "/{project_id}/dependencies",
    response_model=ProjectDependencyRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_dependency_endpoint(
    project_id: UUID,
    payload: ProjectDependencyCreate,
    session: SessionDependency,
) -> ProjectDependencyRead:
    dependency = await create_project_dependency(session, project_id, payload)
    return ProjectDependencyRead.model_validate(dependency)


@router.patch(
    "/{project_id}/dependencies/{dependency_id}",
    response_model=ProjectDependencyRead,
)
async def update_project_dependency_endpoint(
    project_id: UUID,
    dependency_id: UUID,
    payload: ProjectDependencyUpdate,
    session: SessionDependency,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> ProjectDependencyRead:
    dependency = await update_project_dependency(session, dependency_id, payload, project_id, version_from_if_match(if_match))
    response.headers["ETag"] = etag_for(dependency.version)
    return ProjectDependencyRead.model_validate(dependency)


@router.delete("/{project_id}/dependencies/{dependency_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_dependency_endpoint(
    project_id: UUID,
    dependency_id: UUID,
    session: SessionDependency,
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> None:
    await delete_project_dependency(session, dependency_id, project_id, version_from_if_match(if_match))


@router.post("/import/preview")
async def preview_projects_import(
    session: SessionDependency,
    file: CsvFile,
) -> dict[str, object]:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="Upload a CSV file.")
    return await preview_projects(session, parse_projects(await file.read()))


@router.post("/import")
async def import_projects_endpoint(
    session: SessionDependency,
    file: CsvFile,
) -> dict[str, object]:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="Upload a CSV file.")
    parsed = parse_projects(await file.read())
    preview = await preview_projects(session, parsed)
    if preview["issues"]:
        raise HTTPException(
            status_code=422,
            detail={"message": "CSV validation failed.", "issues": preview["issues"]},
        )
    return {"entity": "projects", **await commit_projects(session, parsed)}


@router.delete("/{project_id}", response_model=ProjectRead)
async def delete_project_endpoint(
    project_id: UUID,
    session: SessionDependency,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> ProjectRead:
    project = await deactivate_project(session, project_id, version_from_if_match(if_match))
    response.headers["ETag"] = etag_for(project.version)
    return ProjectRead.model_validate(project)
