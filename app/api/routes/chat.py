from fastapi import APIRouter, Request

from app.api.schemas.chat import ChatRequest, ChatResponse
from app.application.chat_service import send_chat_message

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/messages", response_model=ChatResponse)
async def create_chat_message(payload: ChatRequest, request: Request) -> ChatResponse:
    correlation_id = request.scope.get("correlation_id")
    return await send_chat_message(
        payload,
        correlation_id if isinstance(correlation_id, str) else None,
    )
