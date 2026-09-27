import pytest
from fastapi import HTTPException
import httpx

from app.api.schemas.chat import ChatRequest
from app.core.config import Settings
from app.infrastructure.integrations import genai_client
from app.infrastructure.integrations.genai_client import GenAIClient


@pytest.mark.asyncio
async def test_chat_fails_closed_when_model_is_not_configured() -> None:
    client = GenAIClient(
        Settings(
            genai_model_endpoint=None,
            genai_api_key=None,
        )
    )

    with pytest.raises(HTTPException) as error:
        await client.chat(
            ChatRequest(messages=[{"role": "user", "content": "Olá"}]),
            correlation_id="test-correlation",
        )

    assert error.value.status_code == 503


def test_chat_parses_openai_compatible_response() -> None:
    client = GenAIClient(
        Settings(
            GENAI_MODEL_ENDPOINT="https://example.test/chat/completions",
            GENAI_API_KEY="not-a-real-key",
        )
    )

    response = client.parse_response(
        {
            "model": "gpt-test",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Resposta"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 2,
                "total_tokens": 3,
            },
        },
        correlation_id="corr-1",
    )

    assert response.content == "Resposta"
    assert response.model == "gpt-test"
    assert response.finish_reason == "stop"
    assert response.usage is not None
    assert response.usage.total_tokens == 3
    assert response.correlation_id == "corr-1"


@pytest.mark.asyncio
async def test_chat_retries_with_max_completion_tokens_when_provider_requires_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = [
        httpx.Response(
            status_code=400,
            json={"error": {"message": "Use max_completion_tokens instead of max_tokens."}},
            request=httpx.Request("POST", "https://example.test/chat/completions"),
        ),
        httpx.Response(
            status_code=200,
            json={
                "model": "gpt-test",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "READY"},
                        "finish_reason": "stop",
                    }
                ],
            },
            request=httpx.Request("POST", "https://example.test/chat/completions"),
        ),
    ]
    payloads: list[dict[str, object]] = []

    class FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]) -> httpx.Response:
            payloads.append(dict(json))
            return responses.pop(0)

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    client = GenAIClient(
        Settings(
            GENAI_MODEL_ENDPOINT="https://example.test/chat/completions",
            GENAI_API_KEY="not-a-real-key",
            GENAI_MODEL_NAME="gpt-test",
        )
    )

    response = await client.chat(
        ChatRequest(messages=[{"role": "user", "content": "Olá"}], max_tokens=42),
        correlation_id="corr-2",
    )

    assert response.content == "READY"
    assert len(payloads) == 2
    assert payloads[0]["max_tokens"] == 42
    assert "max_completion_tokens" not in payloads[0]
    assert payloads[1]["max_completion_tokens"] == 42
    assert "max_tokens" not in payloads[1]


@pytest.mark.asyncio
async def test_chat_executes_tool_calls_until_final_response(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [
        httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "create_project",
                                        "arguments": '{"code":"DCM-2","name":"Portal Upgrade","business_area":"BEFS","project_type":"STANDARD"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "model": "gpt-test",
            },
            request=httpx.Request("POST", "https://example.test/chat/completions"),
        ),
        httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "Projeto criado com sucesso."},
                        "finish_reason": "stop",
                    }
                ],
                "model": "gpt-test",
            },
            request=httpx.Request("POST", "https://example.test/chat/completions"),
        ),
    ]
    payloads: list[dict[str, object]] = []

    class FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]) -> httpx.Response:
            payloads.append(dict(json))
            return responses.pop(0)

    async def fake_execute_tool_calls(
        self: GenAIClient,
        tool_calls: list[dict[str, object]],
    ) -> list[dict[str, str]]:
        assert tool_calls[0]["id"] == "call_1"
        return [
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "content": '{"ok": true, "tool": "create_project", "result": {"action": "created"}}',
            }
        ]

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(GenAIClient, "execute_tool_calls", fake_execute_tool_calls)

    client = GenAIClient(
        Settings(
            GENAI_MODEL_ENDPOINT="https://example.test/chat/completions",
            GENAI_API_KEY="not-a-real-key",
            GENAI_MODEL_NAME="gpt-test",
        )
    )

    response = await client.chat(
        ChatRequest(messages=[{"role": "user", "content": "Cria um projeto novo."}], max_tokens=120),
        correlation_id="corr-3",
    )

    assert response.content == "Projeto criado com sucesso."
    assert len(payloads) == 2
    assert "tools" in payloads[0]
    second_messages = payloads[1]["messages"]
    assert isinstance(second_messages, list)
    assert second_messages[-1]["role"] == "tool"
