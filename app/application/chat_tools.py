import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.capacity import (
    AllocationCreate,
    AllocationRead,
    CalendarWeekRead,
    ProjectCreate,
    ProjectRead,
    ResourceCreate,
    ResourceRead,
)
from app.application.capacity_service import (
    create_allocation,
    create_project,
    create_resource,
    deactivate_project,
    list_calendar_weeks,
    list_projects,
    list_resources,
)
from app.domain.enums import (
    AllocationType,
    BusinessArea,
    DeliveryModel,
    Discipline,
    LifecycleState,
    Priority,
    ProjectType,
    ResourceRoleType,
    ResourceStatus,
)
from app.domain.models import CalendarWeek, Project, Resource, normalize_code


def enum_values(enum_type: type[Any]) -> list[str]:
    return [member.value for member in enum_type]


CHAT_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_projects",
            "description": "List active projects available for allocation and management.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_project",
            "description": "Create a new project from structured business data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": ["string", "null"]},
                    "business_area": {"type": "string", "enum": enum_values(BusinessArea)},
                    "project_type": {"type": "string", "enum": enum_values(ProjectType)},
                    "lifecycle_state": {"type": "string", "enum": enum_values(LifecycleState)},
                    "priority": {"type": "string", "enum": enum_values(Priority)},
                    "delivery_model": {"type": "string", "enum": enum_values(DeliveryModel)},
                    "start_date": {
                        "type": ["string", "null"],
                        "description": "ISO date YYYY-MM-DD",
                    },
                    "target_end_date": {
                        "type": ["string", "null"],
                        "description": "ISO date YYYY-MM-DD",
                    },
                },
                "required": ["code", "name", "business_area", "project_type"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_project",
            "description": "Soft-delete a project by deactivating it. Prefer project_code when the user refers to the project business code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": ["string", "null"]},
                    "project_code": {"type": ["string", "null"]},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_developers",
            "description": "List active developers/resources available for planning.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_developer",
            "description": "Create a new developer/resource that can be allocated to projects.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": ["string", "null"]},
                    "discipline": {"type": "string", "enum": enum_values(Discipline)},
                    "role_type": {"type": "string", "enum": enum_values(ResourceRoleType)},
                    "specialization": {"type": ["string", "null"]},
                    "seniority": {"type": ["string", "null"]},
                    "default_weekly_capacity": {"type": "number"},
                    "status": {"type": "string", "enum": enum_values(ResourceStatus)},
                },
                "required": ["name", "discipline", "role_type"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_calendar_weeks",
            "description": "List calendar weeks to support allocations. Use this before allocating if the user does not specify an exact ISO week.",
            "parameters": {
                "type": "object",
                "properties": {
                    "iso_year": {"type": ["integer", "null"]},
                    "limit": {"type": ["integer", "null"], "minimum": 1, "maximum": 52},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "allocate_developer_to_project",
            "description": "Allocate a developer to a project for a specific ISO week. The tool can resolve developer by id, email or exact name, project by id or code, and week by calendar_week_id or ISO year plus ISO week.",
            "parameters": {
                "type": "object",
                "properties": {
                    "resource_id": {"type": ["string", "null"]},
                    "resource_email": {"type": ["string", "null"]},
                    "resource_name": {"type": ["string", "null"]},
                    "project_id": {"type": ["string", "null"]},
                    "project_code": {"type": ["string", "null"]},
                    "calendar_week_id": {"type": ["string", "null"]},
                    "iso_year": {"type": ["integer", "null"]},
                    "iso_week": {"type": ["integer", "null"], "minimum": 1, "maximum": 53},
                    "percentage": {"type": "number", "exclusiveMinimum": 0, "maximum": 150},
                    "notes": {"type": ["string", "null"]},
                },
                "required": ["percentage"],
                "additionalProperties": False,
            },
        },
    },
]


class ChatToolExecutor:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(self, tool_name: str, arguments_json: str) -> dict[str, Any]:
        arguments = self.parse_arguments(arguments_json)
        handlers = {
            "list_projects": self.list_projects,
            "create_project": self.create_project,
            "delete_project": self.delete_project,
            "list_developers": self.list_developers,
            "create_developer": self.create_developer,
            "list_calendar_weeks": self.list_calendar_weeks,
            "allocate_developer_to_project": self.allocate_developer_to_project,
        }
        handler = handlers.get(tool_name)
        if handler is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unsupported tool '{tool_name}'.",
            )
        return await handler(arguments)

    async def list_projects(self, _: dict[str, Any]) -> dict[str, Any]:
        projects = await list_projects(self.session)
        active_projects = [project for project in projects if project.active]
        return {"projects": [self.serialize_project(project) for project in active_projects]}

    async def create_project(self, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = ProjectCreate(**arguments)
        project = await create_project(self.session, payload)
        return {
            "action": "created",
            "project": self.serialize_project(project),
        }

    async def delete_project(self, arguments: dict[str, Any]) -> dict[str, Any]:
        project = await self.resolve_project(
            project_id=arguments.get("project_id"),
            project_code=arguments.get("project_code"),
        )
        project = await deactivate_project(self.session, project.id)
        return {
            "action": "deactivated",
            "project": self.serialize_project(project),
        }

    async def list_developers(self, _: dict[str, Any]) -> dict[str, Any]:
        developers = await list_resources(self.session)
        active_developers = [resource for resource in developers if resource.active]
        return {"developers": [self.serialize_resource(resource) for resource in active_developers]}

    async def create_developer(self, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = ResourceCreate(**arguments)
        developer = await create_resource(self.session, payload)
        return {
            "action": "created",
            "developer": self.serialize_resource(developer),
        }

    async def list_calendar_weeks(self, arguments: dict[str, Any]) -> dict[str, Any]:
        iso_year = arguments.get("iso_year")
        raw_limit = arguments.get("limit")
        limit = int(raw_limit) if raw_limit is not None else 12
        weeks = await list_calendar_weeks(self.session)
        if iso_year is not None:
            weeks = [week for week in weeks if week.iso_year == iso_year]
        else:
            lower_bound = datetime.now(UTC).date() - timedelta(days=14)
            weeks = [week for week in weeks if week.end_date >= lower_bound]
        weeks = weeks[:limit]
        return {"calendar_weeks": [self.serialize_calendar_week(week) for week in weeks]}

    async def allocate_developer_to_project(self, arguments: dict[str, Any]) -> dict[str, Any]:
        resource = await self.resolve_resource(
            resource_id=arguments.get("resource_id"),
            resource_email=arguments.get("resource_email"),
            resource_name=arguments.get("resource_name"),
        )
        project = await self.resolve_project(
            project_id=arguments.get("project_id"),
            project_code=arguments.get("project_code"),
        )
        week = await self.resolve_calendar_week(
            calendar_week_id=arguments.get("calendar_week_id"),
            iso_year=arguments.get("iso_year"),
            iso_week=arguments.get("iso_week"),
        )

        payload = AllocationCreate(
            resource_id=resource.id,
            project_id=project.id,
            calendar_week_id=week.id,
            allocation_type=AllocationType.PROJECT,
            percentage=Decimal(str(arguments["percentage"])),
            notes=arguments.get("notes"),
        )
        allocation = await create_allocation(self.session, payload)
        return {
            "action": "allocated",
            "allocation": self.serialize_allocation(allocation),
            "resource": self.serialize_resource(resource),
            "project": self.serialize_project(project),
            "calendar_week": self.serialize_calendar_week(week),
        }

    async def resolve_project(
        self,
        *,
        project_id: str | None,
        project_code: str | None,
    ) -> Project:
        if project_id:
            project = await self.session.get(Project, UUID(project_id))
            if project is None or not project.active:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
            return project

        if project_code:
            statement = select(Project).where(Project.code_normalized == normalize_code(project_code))
            project = await self.session.scalar(statement)
            if project is None or not project.active:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
            return project

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="project_id or project_code is required.",
        )

    async def resolve_resource(
        self,
        *,
        resource_id: str | None,
        resource_email: str | None,
        resource_name: str | None,
    ) -> Resource:
        if resource_id:
            resource = await self.session.get(Resource, UUID(resource_id))
            if resource is None or not resource.active:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found.")
            return resource

        if resource_email:
            statement = select(Resource).where(Resource.email == resource_email.strip())
            resource = await self.session.scalar(statement)
            if resource is None or not resource.active:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found.")
            return resource

        if resource_name:
            statement = select(Resource).where(Resource.name == resource_name.strip())
            resource = await self.session.scalar(statement)
            if resource is None or not resource.active:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found.")
            return resource

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="resource_id, resource_email or resource_name is required.",
        )

    async def resolve_calendar_week(
        self,
        *,
        calendar_week_id: str | None,
        iso_year: int | None,
        iso_week: int | None,
    ) -> CalendarWeek:
        if calendar_week_id:
            week = await self.session.get(CalendarWeek, UUID(calendar_week_id))
            if week is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Calendar week not found.",
                )
            return week

        if iso_year is not None and iso_week is not None:
            statement = select(CalendarWeek).where(
                CalendarWeek.iso_year == iso_year,
                CalendarWeek.iso_week == iso_week,
            )
            week = await self.session.scalar(statement)
            if week is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Calendar week not found.",
                )
            return week

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="calendar_week_id or iso_year plus iso_week is required.",
        )

    def parse_arguments(self, arguments_json: str) -> dict[str, Any]:
        try:
            arguments = json.loads(arguments_json or "{}")
        except json.JSONDecodeError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Tool arguments are not valid JSON.",
            ) from error

        if not isinstance(arguments, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Tool arguments must be a JSON object.",
            )
        return arguments

    def serialize_project(self, project: Project) -> dict[str, Any]:
        return ProjectRead.model_validate(project).model_dump(mode="json")

    def serialize_resource(self, resource: Resource) -> dict[str, Any]:
        return ResourceRead.model_validate(resource).model_dump(mode="json")

    def serialize_calendar_week(self, week: CalendarWeek) -> dict[str, Any]:
        return CalendarWeekRead.model_validate(week).model_dump(mode="json")

    def serialize_allocation(self, allocation: Any) -> dict[str, Any]:
        return AllocationRead.model_validate(allocation).model_dump(mode="json")