from app.application.import_service import parse_projects, parse_resources


def test_parse_resources_accepts_csv_and_defaults_optional_values() -> None:
    parsed = parse_resources(
        b"name,email,discipline,role_type\nAna Silva,ana@example.com,BACKEND,BACKEND_DEVELOPER\n"
    )

    assert parsed.issues == []
    assert len(parsed.rows) == 1
    assert parsed.rows[0]["payload"].default_weekly_capacity == 100


def test_parse_resources_reports_row_and_field_for_invalid_values() -> None:
    parsed = parse_resources(
        b"name,email,discipline,role_type,default_weekly_capacity\nAna,,WRONG,BACKEND_DEVELOPER,200\n"
    )

    assert {(issue.row, issue.field) for issue in parsed.issues} == {
        (2, "email"),
        (2, "discipline"),
        (2, "default_weekly_capacity"),
    }


def test_parse_projects_supports_semicolon_delimiter_and_defaults() -> None:
    parsed = parse_projects(
        b"code;name;business_area;project_type\nP-001;Portal;BEFS;STANDARD\n"
    )

    assert parsed.issues == []
    assert parsed.rows[0]["payload"].lifecycle_state.value == "IDENTIFIED"


def test_parse_projects_accepts_dates_without_trailing_zeroes() -> None:
    parsed = parse_projects(
        b"code,name,business_area,project_type,start_date,target_end_date\n"
        b"P-001,Portal,BEFS,STANDARD,2026-9-1,2026-12-5\n"
    )

    assert parsed.issues == []
    assert parsed.rows[0]["payload"].start_date.isoformat() == "2026-09-01"
    assert parsed.rows[0]["payload"].target_end_date.isoformat() == "2026-12-05"


def test_parse_projects_reports_invalid_date_format() -> None:
    parsed = parse_projects(
        b"code,name,business_area,project_type,start_date\n"
        b"P-001,Portal,BEFS,STANDARD,01/09/2026\n"
    )

    assert len(parsed.issues) == 1
    assert parsed.issues[0].field == "dates"
