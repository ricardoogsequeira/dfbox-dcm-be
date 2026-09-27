from contextvars import ContextVar
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

CORRELATION_HEADER = "X-Correlation-ID"
current_correlation_id: ContextVar[str | None] = ContextVar("current_correlation_id", default=None)


class CorrelationIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        correlation_id = headers.get(
            CORRELATION_HEADER.lower().encode(), uuid4().hex.encode()
        ).decode()
        scope["correlation_id"] = correlation_id
        token = current_correlation_id.set(correlation_id)

        async def send_with_correlation(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))
                response_headers.append(
                    (CORRELATION_HEADER.lower().encode(), correlation_id.encode())
                )
                message["headers"] = response_headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_correlation)
        finally:
            current_correlation_id.reset(token)
