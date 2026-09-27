import uuid

import pytest
from fastapi import HTTPException

from app.application import capacity_service
from app.domain.models import Project


class FakeProjectSession:
    def __init__(self, project: Project | None) -> None:
        self.project = project
        self.committed = False
        self.audit_events = []

    def add(self, item: object) -> None:
        self.audit_events.append(item)

    async def get(self, model: type[Project], entity_id: uuid.UUID, **kwargs: object) -> Project | None:
        if self.project is not None and self.project.id == entity_id:
            return self.project
        return None

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.committed = False

    async def refresh(self, _: Project) -> None:
        return None


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
        version=1,
    )


@pytest.mark.asyncio
async def test_deactivate_project_marks_project_inactive() -> None:
    project = build_project()
    session = FakeProjectSession(project)

    updated_project = await capacity_service.deactivate_project(session, project.id)  # type: ignore[arg-type]

    assert updated_project.active is False
    assert updated_project.version == 2
    assert session.committed is True


@pytest.mark.asyncio
async def test_deactivate_project_returns_not_found_for_missing_project() -> None:
    session = FakeProjectSession(None)

    with pytest.raises(HTTPException) as error:
        await capacity_service.deactivate_project(session, uuid.uuid4())  # type: ignore[arg-type]

    assert error.value.status_code == 404
