from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from app.core.concurrency import etag_for, require_version, version_from_if_match
from app.domain.models import ProjectDependency
from app.application.audit_service import record_audit
from app.middleware.correlation import current_correlation_id


def test_if_match_parsing_and_etag() -> None:
    assert etag_for(7) == '"7"'
    assert version_from_if_match('W/"7"') == 7

    with pytest.raises(HTTPException) as missing:
        version_from_if_match(None)
    assert missing.value.status_code == 428

    with pytest.raises(HTTPException) as malformed:
        version_from_if_match('not-a-version')
    assert malformed.value.status_code == 400


def test_if_match_rejects_stale_version() -> None:
    with pytest.raises(HTTPException) as error:
        require_version(actual=3, expected=2)
    assert error.value.status_code == 412


@pytest.mark.asyncio
async def test_audit_is_enlisted_without_committing_and_keeps_correlation() -> None:
    class Session:
        def __init__(self) -> None:
            self.items = []
            self.commits = 0

        def add(self, item: object) -> None:
            self.items.append(item)

    session = Session()
    token = current_correlation_id.set("corr-test")
    try:
        await record_audit(session, entity_type="Project", entity_id="project-1", action="UPDATE")  # type: ignore[arg-type]
    finally:
        current_correlation_id.reset(token)

    assert session.commits == 0
    assert len(session.items) == 1
    assert session.items[0].correlation_id == "corr-test"  # type: ignore[union-attr]


@pytest.mark.parametrize(('status', 'impact', 'is_open'), [
    ('OPEN', 'HIGH', True),
    ('IN_PROGRESS', 'CRITICAL', True),
    ('BLOCKED', 'CRITICAL', True),
    ('RESOLVED', 'CRITICAL', False),
    ('CANCELLED', 'CRITICAL', False),
])
def test_dependency_computed_risk_fields(status: str, impact: str, is_open: bool) -> None:
    dependency = ProjectDependency(
        status=status,
        impact_level=impact,
        target_date=date.today() - timedelta(days=1),
        start_date=date.today() - timedelta(days=3),
    )

    assert dependency.is_open is is_open
    assert dependency.is_overdue is is_open
    assert dependency.is_critical_open is (is_open and impact == 'CRITICAL')
