import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi import HTTPException

from app.api.schemas.capacity import AllocationCreate
from app.application import capacity_service
from app.domain.enums import AllocationType
from app.domain.models import Allocation, CalendarWeek, Project, Resource


class FakeSession:
    def __init__(
        self,
        *,
        resource: Resource | None,
        week: CalendarWeek | None,
        project: Project | None,
    ) -> None:
        self.resource = resource
        self.week = week
        self.project = project
        self.added: list[Any] = []
        self.committed = False

    async def get(self, model: type[Any], entity_id: uuid.UUID, **_: Any) -> Any:
        if model is Resource and self.resource and self.resource.id == entity_id:
            return self.resource
        if model is CalendarWeek and self.week and self.week.id == entity_id:
            return self.week
        if model is Project and self.project and self.project.id == entity_id:
            return self.project
        return None

    def add(self, entity: Any) -> None:
        self.added.append(entity)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.committed = False

    async def refresh(self, _: Any) -> None:
        return None


def build_resource() -> Resource:
    return Resource(
        id=uuid.uuid4(),
        name="Developer One",
        discipline="BACKEND",
        role_type="BACKEND_DEVELOPER",
        default_weekly_capacity=Decimal("100.00"),
        status="AVAILABLE",
        active=True,
    )


def build_week() -> CalendarWeek:
    return CalendarWeek(
        id=uuid.uuid4(),
        iso_year=2026,
        iso_week=39,
        start_date=date(2026, 9, 21),
        end_date=date(2026, 9, 27),
    )


def build_project() -> Project:
    return Project(
        id=uuid.uuid4(),
        code="DCM",
        code_normalized="dcm",
        name="Delivery Capacity Manager",
        business_area="BEFS",
        project_type="STANDARD",
        lifecycle_state="IDENTIFIED",
        priority="MEDIUM",
        delivery_model="INTERNAL",
        active=True,
    )


@pytest.mark.asyncio
async def test_project_allocation_requires_project_id() -> None:
    resource = build_resource()
    week = build_week()
    session = FakeSession(resource=resource, week=week, project=None)

    with pytest.raises(HTTPException) as error:
        await capacity_service.create_allocation(
            session,  # type: ignore[arg-type]
            AllocationCreate(
                resource_id=resource.id,
                calendar_week_id=week.id,
                allocation_type=AllocationType.PROJECT,
                percentage=Decimal("50.00"),
            ),
        )

    assert error.value.status_code == 422
    assert not session.committed


@pytest.mark.asyncio
async def test_allocation_rejects_weekly_total_above_150(monkeypatch: pytest.MonkeyPatch) -> None:
    resource = build_resource()
    week = build_week()
    project = build_project()
    session = FakeSession(resource=resource, week=week, project=project)

    async def current_total(*_: Any, **__: Any) -> Decimal:
        return Decimal("120.00")

    monkeypatch.setattr(capacity_service, "current_allocated_percentage", current_total)

    with pytest.raises(HTTPException) as error:
        await capacity_service.create_allocation(
            session,  # type: ignore[arg-type]
            AllocationCreate(
                resource_id=resource.id,
                project_id=project.id,
                calendar_week_id=week.id,
                allocation_type=AllocationType.PROJECT,
                percentage=Decimal("40.00"),
            ),
        )

    assert error.value.status_code == 409
    assert not session.committed


@pytest.mark.asyncio
async def test_allocation_accepts_total_at_150(monkeypatch: pytest.MonkeyPatch) -> None:
    resource = build_resource()
    week = build_week()
    project = build_project()
    session = FakeSession(resource=resource, week=week, project=project)

    async def current_total(*_: Any, **__: Any) -> Decimal:
        return Decimal("100.00")

    monkeypatch.setattr(capacity_service, "current_allocated_percentage", current_total)

    allocation = await capacity_service.create_allocation(
        session,  # type: ignore[arg-type]
        AllocationCreate(
            resource_id=resource.id,
            project_id=project.id,
            calendar_week_id=week.id,
            allocation_type=AllocationType.PROJECT,
            percentage=Decimal("50.00"),
        ),
    )

    assert isinstance(allocation, Allocation)
    assert allocation.percentage == Decimal("50.00")
    assert session.committed
