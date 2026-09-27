from fastapi import HTTPException, status


def etag_for(version: int) -> str:
    return f'"{version}"'


def version_from_if_match(value: str | None) -> int:
    if not value:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header is required.",
        )
    candidate = value.strip().removeprefix("W/").strip('"')
    try:
        return int(candidate)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="If-Match must contain the current entity version.",
        ) from error


def require_version(actual: int, expected: int) -> None:
    if actual != expected:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="The entity changed since it was read. Reload and try again.",
        )
