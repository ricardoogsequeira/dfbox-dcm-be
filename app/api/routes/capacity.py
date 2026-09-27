from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.capacity import (
    CalendarExtendRequest,
    CalendarExtendResponse,
    CalendarWeekCreate,
    CalendarWeekRead,
)
from app.application.capacity_service import (
    create_calendar_week,
    extend_calendar_weeks,
    list_calendar_weeks,
)
from app.core.database import get_db_session

router = APIRouter(prefix="/capacity", tags=["capacity"])
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("/weeks", response_model=CalendarWeekRead, status_code=status.HTTP_201_CREATED)
async def create_calendar_week_endpoint(
    payload: CalendarWeekCreate,
    session: SessionDependency,
) -> CalendarWeekRead:
    week = await create_calendar_week(session, payload)
    return CalendarWeekRead.model_validate(week)


@router.get("/weeks", response_model=list[CalendarWeekRead])
async def list_calendar_weeks_endpoint(session: SessionDependency) -> list[CalendarWeekRead]:
    weeks = await list_calendar_weeks(session)
    return [CalendarWeekRead.model_validate(week) for week in weeks]


@router.post("/weeks/extend", response_model=CalendarExtendResponse)
async def extend_calendar_weeks_endpoint(
    payload: CalendarExtendRequest,
    session: SessionDependency,
) -> CalendarExtendResponse:
    created, total_weeks = await extend_calendar_weeks(session, payload)
    return CalendarExtendResponse(created=created, total_weeks=total_weeks)
