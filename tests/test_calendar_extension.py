from datetime import date

import pytest
from fastapi import HTTPException

from app.api.schemas.capacity import CalendarExtendRequest
from app.application.capacity_service import calendar_week_candidates, extend_calendar_weeks


class EmptyFakeSession:
    async def execute(self, _: object) -> list[tuple[int, int]]:
        return []


@pytest.mark.asyncio
async def test_calendar_extension_requires_an_extension_target() -> None:
    with pytest.raises(HTTPException) as error:
        await extend_calendar_weeks(EmptyFakeSession(), CalendarExtendRequest())  # type: ignore[arg-type]

    assert error.value.status_code == 422


def test_calendar_candidates_until_2030_end_on_last_iso_week() -> None:
    candidates = calendar_week_candidates(CalendarExtendRequest(until_year=2030))

    assert candidates
    assert candidates[-1][0] == 2030
    assert candidates[-1][1] == date(2030, 12, 28).isocalendar().week
    assert all(item[3] >= item[2] for item in candidates)


def test_calendar_candidates_can_start_after_existing_calendar() -> None:
    candidates = calendar_week_candidates(
        CalendarExtendRequest(weeks_ahead=2),
        start_date=date(2030, 12, 29),
    )

    assert candidates[0][2] == date(2030, 12, 30)
    assert candidates[1][2] == date(2031, 1, 6)
