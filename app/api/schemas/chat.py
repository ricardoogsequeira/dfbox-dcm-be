from typing import Literal

from pydantic import BaseModel, Field

ChatRole = Literal["user", "assistant"]


class ChatMessage(BaseModel):
    role: ChatRole
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=800, ge=1, le=4000)


class ChatUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ChatResponse(BaseModel):
    content: str
    model: str | None = None
    finish_reason: str | None = None
    usage: ChatUsage | None = None
    correlation_id: str | None = None
