"""AI router for classroom-grounded instructional guidance."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.dependencies import get_current_active_teacher
from models.user import User
from services.ai_service import build_assessment_ai_context, chat_with_ai

router = APIRouter()

# ── Request / Response schemas ────────────────────────────────────────────────

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    question: str
    assessment_id: Optional[str] = None
    conversation_history: List[Message] = []

class ChartSpec(BaseModel):
    chart_type: str
    metric: str
    title: Optional[str] = None

class ChatResponse(BaseModel):
    response: Optional[str] = None
    chart_spec: Optional[ChartSpec] = None

@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    current_user: User = Depends(get_current_active_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Send a message to the AI instructional assistant."""
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question is required")

    if not req.assessment_id or not req.assessment_id.strip():
        return ChatResponse(
            response="Select an assessment before asking for data-driven intervention guidance.",
            chart_spec=None,
        )

    try:
        assessment_uuid = UUID(req.assessment_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid assessment_id")

    try:
        assessment_context = await build_assessment_ai_context(assessment_uuid, current_user, db)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    history = [
        {"role": msg.role, "content": msg.content}
        for msg in req.conversation_history
        if msg.role in ("user", "assistant") and (msg.content or "").strip()
    ]
    result = await chat_with_ai(question=question, assessment_context=assessment_context, conversation_history=history)
    return ChatResponse(response=result.get("response"), chart_spec=result.get("chart_spec"))
