from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.capacity import (
    AllocationCreate,
    AllocationUpdate,
    AllocationRangeCreate,
    AllocationRangeRead,
    AllocationRangeUpdate,
    AllocationRangeUpdateRead,
    AllocationRead,
)
from app.application.capacity_service import (
    create_allocation,
    create_allocation_range,
    delete_allocation,
    list_allocations,
    update_allocation,
    update_allocation_range,
)
from app.core.database import get_db_session
from app.core.concurrency import etag_for, version_from_if_match

router = APIRouter(prefix="/allocations", tags=["allocations"])
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("", response_model=AllocationRead, status_code=status.HTTP_201_CREATED)
async def create_allocation_endpoint(
    payload: AllocationCreate,
    session: SessionDependency,
) -> AllocationRead:
    allocation = await create_allocation(session, payload)
    return AllocationRead.model_validate(allocation)


@router.get("", response_model=list[AllocationRead])
async def list_allocations_endpoint(session: SessionDependency) -> list[AllocationRead]:
    allocations = await list_allocations(session)
    return [AllocationRead.model_validate(allocation) for allocation in allocations]


@router.post("/range", response_model=AllocationRangeRead, status_code=status.HTTP_201_CREATED)
async def create_allocation_range_endpoint(
    payload: AllocationRangeCreate,
    session: SessionDependency,
) -> AllocationRangeRead:
    allocations = await create_allocation_range(session, payload)
    return AllocationRangeRead(
        created=len(allocations),
        allocations=[AllocationRead.model_validate(allocation) for allocation in allocations],
    )




@router.patch("/range", response_model=AllocationRangeUpdateRead)
async def update_allocation_range_endpoint(
    payload: AllocationRangeUpdate,
    session: SessionDependency,
) -> AllocationRangeUpdateRead:
    created, deleted = await update_allocation_range(session, payload)
    return AllocationRangeUpdateRead(created=created, deleted=deleted)


@router.patch("/{allocation_id}", response_model=AllocationRead)
async def update_allocation_endpoint(
    allocation_id: UUID,
    payload: AllocationUpdate,
    session: SessionDependency,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> AllocationRead:
    allocation = await update_allocation(
        session, allocation_id, payload, version_from_if_match(if_match)
    )
    response.headers["ETag"] = etag_for(allocation.version)
    return AllocationRead.model_validate(allocation)


@router.delete("/{allocation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_allocation_endpoint(
    allocation_id: UUID,
    session: SessionDependency,
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> Response:
    await delete_allocation(session, allocation_id, version_from_if_match(if_match))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
