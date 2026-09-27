from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status


async def validation_exception_handler(
    _: Request,
    exception: Exception,
) -> JSONResponse:
    if not isinstance(exception, RequestValidationError):
        return problem_detail(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal server error",
            detail="An unexpected error occurred.",
            instance="",
        )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "type": "https://httpstatuses.com/422",
            "title": "Request validation failed",
            "status": 422,
            "detail": "The request contains invalid data.",
            "errors": exception.errors(),
        },
        media_type="application/problem+json",
    )


def problem_detail(
    *,
    status_code: int,
    title: str,
    detail: str,
    instance: str,
    **extensions: Any,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "type": f"https://httpstatuses.com/{status_code}",
            "title": title,
            "status": status_code,
            "detail": detail,
            "instance": instance,
            **extensions,
        },
        media_type="application/problem+json",
    )
