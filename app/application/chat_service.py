from app.api.schemas.chat import ChatRequest, ChatResponse
from app.core.config import get_settings
from app.infrastructure.integrations.genai_client import GenAIClient


async def send_chat_message(request: ChatRequest, correlation_id: str | None) -> ChatResponse:
    client = GenAIClient(get_settings())
    return await client.chat(request, correlation_id)
