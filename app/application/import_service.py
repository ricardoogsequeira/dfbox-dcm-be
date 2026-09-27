import csv
import io
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.capacity import ProjectCreate, ResourceCreate
from app.domain.enums import (
    BusinessArea,
    DeliveryModel,
    Discipline,
    LifecycleState,
    Priority,
    ProjectType,
    ResourceRoleType,
    ResourceStatus,
)
from app.domain.models import Project, Resource, normalize_code

MAX_IMPORT_ROWS = 5000


@dataclass(frozen=True)
class ImportIssue:
    row: int
    field: str
    message: str


@dataclass(frozen=True)
class ParsedImport:
    rows: list[dict[str, Any]]
    issues: list[ImportIssue]


def _normalise_header(value: str) -> str:
    return value.strip().casefold().replace(" ", "_")


def _normalise_enum(value: str) -> str:
    return value.strip().upper().replace("-", "_").replace(" ", "_")


def _normalise_date(value: str) -> date | None:
    value = value.strip()
    if not value:
        return None
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", value)
    if not match:
        raise ValueError("Use a data no formato YYYY-M-D ou YYYY-MM-DD.")
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError as error:
        raise ValueError("A data indicada não é válida.") from error


def _read_csv(content: bytes) -> tuple[list[dict[str, str]], list[ImportIssue]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], [ImportIssue(1, "file", "O ficheiro deve estar codificado em UTF-8.")]

    if not text.strip():
        return [], [ImportIssue(1, "file", "O ficheiro CSV está vazio.")]

    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        return [], [ImportIssue(1, "headers", "O CSV tem de incluir cabeçalhos.")]

    reader.fieldnames = [_normalise_header(value or "") for value in reader.fieldnames]
    rows: list[dict[str, str]] = []
    issues: list[ImportIssue] = []
    for row_number, raw_row in enumerate(reader, start=2):
        if row_number > MAX_IMPORT_ROWS + 1:
            issues.append(
                ImportIssue(row_number, "file", f"O limite é de {MAX_IMPORT_ROWS} linhas.")
            )
            break
        rows.append({key: (value or "").strip() for key, value in raw_row.items() if key})
    if not rows:
        issues.append(ImportIssue(2, "file", "O CSV tem de incluir pelo menos uma linha de dados."))
    return rows, issues


def _required(row: dict[str, str], row_number: int, field: str, issues: list[ImportIssue]) -> str:
    value = row.get(field, "").strip()
    if not value:
        issues.append(ImportIssue(row_number, field, "Campo obrigatório."))
    return value


def _enum_value(
    row: dict[str, str],
    row_number: int,
    field: str,
    enum_type: type[Any],
    issues: list[ImportIssue],
    default: str | None = None,
) -> str | None:
    raw = row.get(field, "").strip()
    if not raw and default is not None:
        return default
    value = _normalise_enum(raw)
    if value not in {member.value for member in enum_type}:
        issues.append(ImportIssue(row_number, field, f"Valor inválido: {raw or '(vazio)'}"))
        return None
    return value


def parse_resources(content: bytes) -> ParsedImport:
    source_rows, issues = _read_csv(content)
    parsed: list[dict[str, Any]] = []
    for row_number, row in enumerate(source_rows, start=2):
        name = _required(row, row_number, "name", issues)
        email = _required(row, row_number, "email", issues)
        discipline = _enum_value(row, row_number, "discipline", Discipline, issues)
        role_type = _enum_value(row, row_number, "role_type", ResourceRoleType, issues)
        status = _enum_value(
            row, row_number, "status", ResourceStatus, issues, ResourceStatus.AVAILABLE.value
        )
        capacity_raw = row.get("default_weekly_capacity", "100").strip() or "100"
        try:
            capacity = Decimal(capacity_raw.replace(",", "."))
            if capacity < 0 or capacity > 150:
                raise InvalidOperation
        except InvalidOperation:
            issues.append(
                ImportIssue(row_number, "default_weekly_capacity", "Use um número entre 0 e 150.")
            )
            capacity = Decimal("100")
        if name and email and discipline and role_type and status:
            parsed.append(
                {
                    "row": row_number,
                    "payload": ResourceCreate(
                        name=name,
                        company=row.get("company", "").strip() or "EDP",
                        email=email,
                        discipline=discipline,
                        role_type=role_type,
                        specialization=row.get("specialization") or None,
                        seniority=row.get("seniority") or None,
                        default_weekly_capacity=capacity,
                        status=status,
                    ),
                }
            )
    return ParsedImport(parsed, issues)


def parse_projects(content: bytes) -> ParsedImport:
    source_rows, issues = _read_csv(content)
    parsed: list[dict[str, Any]] = []
    for row_number, row in enumerate(source_rows, start=2):
        code = _required(row, row_number, "code", issues)
        name = _required(row, row_number, "name", issues)
        business_area = _enum_value(row, row_number, "business_area", BusinessArea, issues)
        project_type = _enum_value(row, row_number, "project_type", ProjectType, issues)
        lifecycle = _enum_value(
            row,
            row_number,
            "lifecycle_state",
            LifecycleState,
            issues,
            LifecycleState.IDENTIFIED.value,
        )
        priority = _enum_value(row, row_number, "priority", Priority, issues, Priority.MEDIUM.value)
        delivery = _enum_value(
            row, row_number, "delivery_model", DeliveryModel, issues, DeliveryModel.INTERNAL.value
        )
        if code and name and business_area and project_type and lifecycle and priority and delivery:
            try:
                start_date = _normalise_date(row.get("start_date", ""))
                target_end_date = _normalise_date(row.get("target_end_date", ""))
                payload = ProjectCreate(
                    code=code,
                    name=name,
                    description=row.get("description") or None,
                    business_area=business_area,
                    project_type=project_type,
                    lifecycle_state=lifecycle,
                    priority=priority,
                    delivery_model=delivery,
                    start_date=start_date,
                    target_end_date=target_end_date,
                )
                parsed.append({"row": row_number, "payload": payload})
            except ValueError as error:
                issues.append(ImportIssue(row_number, "dates", str(error)))
    return ParsedImport(parsed, issues)


async def preview_resources(session: AsyncSession, parsed: ParsedImport) -> dict[str, Any]:
    existing = {
        resource.email.casefold(): resource
        for resource in (await session.scalars(select(Resource))).all()
        if resource.email
    }
    seen: set[str] = set()
    issues = list(parsed.issues)
    for item in parsed.rows:
        email = item["payload"].email.casefold()
        if email in seen:
            issues.append(ImportIssue(item["row"], "email", "Email repetido no ficheiro."))
        seen.add(email)
        if email in existing:
            item["action"] = "update"
    return {
        "entity": "developers",
        "total": len(parsed.rows),
        "creates": sum("action" not in item for item in parsed.rows),
        "updates": sum(item.get("action") == "update" for item in parsed.rows),
        "issues": [issue.__dict__ for issue in issues],
    }


async def preview_projects(session: AsyncSession, parsed: ParsedImport) -> dict[str, Any]:
    existing = {
        project.code_normalized for project in (await session.scalars(select(Project))).all()
    }
    seen: set[str] = set()
    issues = list(parsed.issues)
    for item in parsed.rows:
        code = normalize_code(item["payload"].code)
        if code in seen:
            issues.append(ImportIssue(item["row"], "code", "Código repetido no ficheiro."))
        seen.add(code)
        if code in existing:
            item["action"] = "update"
    return {
        "entity": "projects",
        "total": len(parsed.rows),
        "creates": sum("action" not in item for item in parsed.rows),
        "updates": sum(item.get("action") == "update" for item in parsed.rows),
        "issues": [issue.__dict__ for issue in issues],
    }


async def commit_resources(session: AsyncSession, parsed: ParsedImport) -> dict[str, int]:
    existing = {
        resource.email.casefold(): resource
        for resource in (await session.scalars(select(Resource))).all()
        if resource.email
    }
    created = updated = 0
    for item in parsed.rows:
        payload: ResourceCreate = item["payload"]
        resource = existing.get(payload.email.casefold() if payload.email else "")
        if resource:
            resource.name = payload.name.strip()
            resource.company = payload.company.strip() or "EDP"
            resource.discipline = payload.discipline.value
            resource.role_type = payload.role_type.value
            resource.specialization = payload.specialization
            resource.seniority = payload.seniority
            resource.default_weekly_capacity = payload.default_weekly_capacity
            resource.status = payload.status.value
            resource.version += 1
            updated += 1
        else:
            session.add(await create_resource_without_commit(session, payload))
            created += 1
    await session.commit()
    return {"created": created, "updated": updated}


async def create_resource_without_commit(
    session: AsyncSession, payload: ResourceCreate
) -> Resource:
    from app.domain.models import Resource

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
    return resource


async def commit_projects(session: AsyncSession, parsed: ParsedImport) -> dict[str, int]:
    existing = {
        project.code_normalized: project
        for project in (await session.scalars(select(Project))).all()
    }
    created = updated = 0
    for item in parsed.rows:
        payload: ProjectCreate = item["payload"]
        project = existing.get(normalize_code(payload.code))
        if project:
            project.name = payload.name.strip()
            project.description = payload.description
            project.business_area = payload.business_area.value
            project.project_type = payload.project_type.value
            project.lifecycle_state = payload.lifecycle_state.value
            project.priority = payload.priority.value
            project.delivery_model = payload.delivery_model.value
            project.start_date = payload.start_date
            project.target_end_date = payload.target_end_date
            project.version += 1
            updated += 1
        else:
            session.add(
                Project(
                    code=payload.code.strip(),
                    code_normalized=normalize_code(payload.code),
                    name=payload.name.strip(),
                    description=payload.description,
                    business_area=payload.business_area.value,
                    project_type=payload.project_type.value,
                    lifecycle_state=payload.lifecycle_state.value,
                    priority=payload.priority.value,
                    delivery_model=payload.delivery_model.value,
                    start_date=payload.start_date,
                    target_end_date=payload.target_end_date,
                )
            )
            created += 1
    await session.commit()
    return {"created": created, "updated": updated}
