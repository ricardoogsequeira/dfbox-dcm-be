from typing import Any
import json

import httpx
from fastapi import HTTPException, status

from app.application.chat_tools import CHAT_TOOL_DEFINITIONS, ChatToolExecutor
from app.api.schemas.chat import ChatRequest, ChatResponse, ChatUsage
from app.core.config import Settings
from app.core.database import async_session_factory

MAX_TOOL_ROUNDS = 4


class GenAIClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def chat(self, request: ChatRequest, correlation_id: str | None) -> ChatResponse:
        if not self.settings.genai_model_endpoint or not self.settings.genai_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GenAI model endpoint is not configured.",
            )

        headers = self.auth_headers()
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id

        messages = self.build_messages(request)

        try:
            async with httpx.AsyncClient(timeout=self.settings.genai_timeout_seconds) as client:
                response_payload = await self.run_conversation(client, headers, messages, request)
        except httpx.TimeoutException as error:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="GenAI model endpoint timed out.",
            ) from error
        except httpx.HTTPStatusError as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="GenAI model endpoint returned an error.",
            ) from error
        except httpx.HTTPError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GenAI model endpoint is unavailable.",
            ) from error

        return self.parse_response(response_payload, correlation_id)

    async def run_conversation(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        messages: list[dict[str, Any]],
        request: ChatRequest,
    ) -> dict[str, Any]:
        for tool_round in range(MAX_TOOL_ROUNDS + 1):
            payload = self.build_payload(messages, request)
            response = await self.post_chat(client, payload, headers)
            if self.should_retry_with_max_completion_tokens(response, payload):
                payload["max_completion_tokens"] = payload.pop("max_tokens")
                response = await self.post_chat(client, payload, headers)
            response.raise_for_status()

            response_payload = response.json()
            tool_calls = self.extract_tool_calls(response_payload)
            if not tool_calls:
                return response_payload

            if tool_round >= MAX_TOOL_ROUNDS:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="GenAI model exceeded the maximum number of tool rounds.",
                )

            messages.append(self.assistant_message_with_tool_calls(response_payload))
            messages.extend(await self.execute_tool_calls(tool_calls))

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GenAI model did not finish the tool workflow.",
        )

    def build_messages(self, request: ChatRequest) -> list[dict[str, Any]]:
        return [
            {"role": "system", "content": self.settings.genai_system_prompt},
            *[message.model_dump() for message in request.messages],
        ]

    def build_payload(
        self,
        messages: list[dict[str, Any]],
        request: ChatRequest,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "tools": CHAT_TOOL_DEFINITIONS,
            "tool_choice": "auto",
        }
        if self.settings.genai_model_name:
            payload["model"] = self.settings.genai_model_name
        return payload

    async def post_chat(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> httpx.Response:
        return await client.post(
            self.settings.genai_model_endpoint,
            json=payload,
            headers=headers,
        )

    def should_retry_with_max_completion_tokens(
        self,
        response: httpx.Response,
        payload: dict[str, Any],
    ) -> bool:
        return (
            response.status_code == status.HTTP_400_BAD_REQUEST
            and "max_tokens" in payload
            and "max_completion_tokens" not in payload
            and "max_completion_tokens" in response.text.lower()
        )

    def extract_tool_calls(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        choice = (payload.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        tool_calls = message.get("tool_calls") or []
        return [tool_call for tool_call in tool_calls if isinstance(tool_call, dict)]

    def assistant_message_with_tool_calls(self, payload: dict[str, Any]) -> dict[str, Any]:
        choice = (payload.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        return {
            "role": "assistant",
            "content": self.extract_message_content(message.get("content")),
            "tool_calls": message.get("tool_calls") or [],
        }

    async def execute_tool_calls(self, tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        async with async_session_factory() as session:
            executor = ChatToolExecutor(session)
            results: list[dict[str, Any]] = []
            for tool_call in tool_calls:
                function = tool_call.get("function") or {}
                tool_name = str(function.get("name") or "")
                arguments_json = str(function.get("arguments") or "{}")
                tool_result = await self.run_tool(executor, tool_name, arguments_json)
                results.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(tool_call.get("id") or ""),
                        "content": json.dumps(tool_result, default=str),
                    }
                )
            return results

    async def run_tool(
        self,
        executor: ChatToolExecutor,
        tool_name: str,
        arguments_json: str,
    ) -> dict[str, Any]:
        try:
            result = await executor.execute(tool_name, arguments_json)
            return {"ok": True, "tool": tool_name, "result": result}
        except HTTPException as error:
            return {
                "ok": False,
                "tool": tool_name,
                "error": {
                    "status_code": error.status_code,
                    "detail": error.detail,
                },
            }

    def auth_headers(self) -> dict[str, str]:
        value = self.settings.genai_api_key or ""
        if self.settings.genai_api_key_prefix:
            value = f"{self.settings.genai_api_key_prefix} {value}"
        return {
            "Content-Type": "application/json",
            self.settings.genai_api_key_header: value,
        }

    def parse_response(self, payload: dict[str, Any], correlation_id: str | None) -> ChatResponse:
        choice = (payload.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        usage = payload.get("usage") or None
        return ChatResponse(
            content=self.extract_message_content(message.get("content")),
            model=payload.get("model"),
            finish_reason=choice.get("finish_reason"),
            usage=ChatUsage(**usage) if usage else None,
            correlation_id=correlation_id,
        )

    def extract_message_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "\n".join(parts)
        return ""
