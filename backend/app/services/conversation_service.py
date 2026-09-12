import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.models import ChatMessage, Conversation, User
from app.services.ollama_service import AIServiceError, build_contextual_messages, generate_chat
from app.services import profile_context_service


def title_from_message(content: str, max_length: int = 72) -> str:
    cleaned = " ".join((content or "").strip().split())
    cleaned = re.sub(r"^[\s\"'`]+|[\s\"'`]+$", "", cleaned)
    if not cleaned:
        return "New conversation"
    if len(cleaned) <= max_length:
        return cleaned
    truncated = cleaned[:max_length].rsplit(" ", 1)[0]
    return (truncated or cleaned[:max_length]).rstrip(".,;:") + "…"


def get_owned_conversation(db: Session, user: User, conversation_id: str) -> Conversation:
    if not conversation_id or not _looks_like_id(conversation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user.id)
        .first()
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    return conversation


def list_conversations(db: Session, user: User) -> list[Conversation]:
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )


def get_conversation_with_messages(db: Session, user: User, conversation_id: str) -> Conversation:
    conversation = (
        db.query(Conversation)
        .options(selectinload(Conversation.messages))
        .filter(Conversation.id == conversation_id, Conversation.user_id == user.id)
        .first()
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    conversation.messages.sort(key=lambda item: item.created_at)
    return conversation


def delete_conversation(db: Session, user: User, conversation_id: str) -> None:
    conversation = get_owned_conversation(db, user, conversation_id)
    db.delete(conversation)
    db.commit()


def _looks_like_id(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def _persist_user_message(db: Session, user: User, content: str, conversation: Conversation | None) -> tuple[Conversation, ChatMessage]:
    if len(content) > settings.AI_MAX_PROMPT_CHARS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Message exceeds the {settings.AI_MAX_PROMPT_CHARS} character limit.",
        )

    if conversation is None:
        conversation = Conversation(
            user_id=user.id,
            title=title_from_message(content),
        )
        db.add(conversation)
        db.flush()

    user_message = ChatMessage(
        conversation_id=conversation.id,
        role="user",
        content=content,
    )
    db.add(user_message)
    conversation.updated_at = datetime.now(timezone.utc)
    db.flush()
    db.refresh(conversation)
    db.refresh(user_message)
    db.commit()
    db.refresh(conversation)
    db.refresh(user_message)
    return conversation, user_message


def _history_for_llm(db: Session, conversation_id: str) -> list[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )


async def send_user_message(
    db: Session,
    user: User,
    content: str,
    conversation: Conversation | None = None,
    think: bool = False,
    use_profile: bool = False,
) -> dict:
    conversation, user_message = _persist_user_message(db, user, content, conversation)
    return await _generate_assistant_reply(
        db,
        user,
        conversation,
        user_message,
        think=think,
        use_profile=use_profile,
    )


async def retry_assistant_reply(
    db: Session,
    user: User,
    conversation_id: str,
    think: bool = False,
) -> dict:
    conversation = get_owned_conversation(db, user, conversation_id)
    history = _history_for_llm(db, conversation.id)
    if not history or history[-1].role != "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="There is no unanswered message to retry.",
        )
    return await _generate_assistant_reply(db, user, conversation, history[-1], think=think)


async def _generate_assistant_reply(
    db: Session,
    user: User,
    conversation: Conversation,
    user_message: ChatMessage,
    think: bool = False,
    use_profile: bool = False,
) -> dict:
    history = _history_for_llm(db, conversation.id)
    profile_context = (
        profile_context_service.build_profile_context(db, user)
        if use_profile
        else None
    )
    ollama_messages = build_contextual_messages(history, profile_context=profile_context)

    try:
        assistant_text = await generate_chat(ollama_messages, think=think)
    except AIServiceError as exc:
        return {
            "conversation": conversation,
            "user_message": user_message,
            "assistant_message": None,
            "error": str(exc),
        }

    assistant_message = ChatMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=assistant_text,
        used_profile_context=use_profile,
    )
    db.add(assistant_message)
    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(conversation)
    db.refresh(assistant_message)
    return {
        "conversation": conversation,
        "user_message": user_message,
        "assistant_message": assistant_message,
        "error": None,
    }
