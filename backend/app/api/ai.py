from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.db.models import User
from app.schemas.ai import (
    AIRequest,
    AIResponse,
    ConversationDetail,
    ConversationSummary,
    GrammarCheckRequest,
    GrammarCheckResponse,
    ProfileOptimizationResponse,
    SendMessageRequest,
    SendMessageResponse,
)
from app.services import conversation_service, languagetool_service, profile_optimizer_service
from app.services import profile_context_service
from app.services.languagetool_service import LanguageToolError
from app.services.ollama_service import AIServiceError, generate_response


router = APIRouter(
    prefix="/ai",
    tags=["AI"],
)


def _to_send_response(payload: dict) -> SendMessageResponse:
    return SendMessageResponse(
        conversation=payload["conversation"],
        user_message=payload["user_message"],
        assistant_message=payload["assistant_message"],
        error=payload.get("error"),
    )


@router.post("/chat", response_model=AIResponse)
async def chat_with_ai(
    request: AIRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prompt = (request.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Prompt cannot be empty.")
    if len(prompt) > settings.AI_MAX_PROMPT_CHARS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Message exceeds the {settings.AI_MAX_PROMPT_CHARS} character limit.",
        )

    try:
        profile_context = (
            profile_context_service.build_profile_context(db, current_user)
            if request.use_profile
            else None
        )
        response = await generate_response(
            prompt=prompt,
            system_prompt=(
                f"{settings.AI_SYSTEM_PROMPT}\n\n{profile_context}"
                if profile_context
                else settings.AI_SYSTEM_PROMPT
            ),
            think=request.think,
        )
        return AIResponse(response=response)
    except AIServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service unavailable.",
        )


@router.post("/profile/optimize", response_model=ProfileOptimizationResponse)
async def optimize_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await profile_optimizer_service.optimize_profile(db, current_user)
    except AIServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is currently unavailable. Please try again later.",
        )


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return conversation_service.list_conversations(db, current_user)


@router.post("/conversations", response_model=SendMessageResponse)
async def start_conversation(
    request: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a conversation on the first user message and return the assistant reply."""
    payload = await conversation_service.send_user_message(
        db=db,
        user=current_user,
        content=request.content,
        conversation=None,
        use_profile=request.use_profile,
    )
    return _to_send_response(payload)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = conversation_service.get_conversation_with_messages(db, current_user, conversation_id)
    return conversation


@router.post("/conversations/{conversation_id}/messages", response_model=SendMessageResponse)
async def send_conversation_message(
    conversation_id: str,
    request: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = conversation_service.get_owned_conversation(db, current_user, conversation_id)
    payload = await conversation_service.send_user_message(
        db=db,
        user=current_user,
        content=request.content,
        conversation=conversation,
        use_profile=request.use_profile,
    )
    return _to_send_response(payload)


@router.post("/conversations/{conversation_id}/retry", response_model=SendMessageResponse)
async def retry_conversation_message(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = await conversation_service.retry_assistant_reply(
        db=db,
        user=current_user,
        conversation_id=conversation_id,
    )
    return _to_send_response(payload)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation_service.delete_conversation(db, current_user, conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/grammar-check", response_model=GrammarCheckResponse)
async def grammar_check(
    request: GrammarCheckRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        result = await languagetool_service.check_text(request.text)
        return GrammarCheckResponse(**result)
    except LanguageToolError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
