from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.services.ai_assistant import get_admin_summary_context, ask_gemini

router = APIRouter(prefix="/admin", tags=["AI Assistant"])

class AIQuestion(BaseModel):
    question: str

class AIResponse(BaseModel):
    answer: str

@router.post("/ai-assistant", response_model=AIResponse)
def get_ai_assistant_response(
    payload: AIQuestion,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Call Gemini AI assistant using only admin-scoped system context data."""
    context = get_admin_summary_context(db, current_admin.id)
    answer = ask_gemini(context, payload.question)
    return AIResponse(answer=answer)
