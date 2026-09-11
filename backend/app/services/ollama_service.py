from ollama import AsyncClient

from app.core.config import settings

client = AsyncClient(host=settings.OLLAMA_BASE_URL)

DEFAULT_SYSTEM_PROMPT = settings.AI_SYSTEM_PROMPT


class AIServiceError(Exception):
    """Raised when the local LLM cannot produce a response."""


async def generate_chat(
    messages: list[dict],
    think: bool = False,
) -> str:
    """Send a multi-turn chat payload to Ollama (Qwen) and return assistant text."""
    try:
        response = await client.chat(
            model=settings.OLLAMA_MODEL,
            messages=messages,
            think=think,
        )
    except Exception as exc:
        raise AIServiceError("The AI model is currently unavailable.") from exc

    message = response.get("message") if isinstance(response, dict) else getattr(response, "message", None)
    if isinstance(message, dict):
        content = message.get("content")
    else:
        content = getattr(message, "content", None) if message is not None else None

    if not isinstance(content, str):
        raise AIServiceError("The AI model returned an unexpected response.")
    return content


async def generate_response(
    prompt: str,
    system_prompt: str | None = None,
    think: bool = False,
) -> str:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    return await generate_chat(messages, think=think)


def build_contextual_messages(
    history: list,
    system_prompt: str | None = None,
) -> list[dict]:
    """
    Build Ollama chat messages from stored turns.
    Keeps the most recent N messages within a character budget.
    System instructions are always first and are not counted in the history window.
    """
    max_messages = max(1, settings.AI_CONTEXT_MESSAGES)
    max_chars = max(1000, settings.AI_CONTEXT_CHARS)

    selected: list[dict] = []
    used_chars = 0
    for item in reversed(history):
        role = item.role if hasattr(item, "role") else item.get("role")
        content = item.content if hasattr(item, "content") else item.get("content")
        if role not in ("user", "assistant") or not content:
            continue
        if len(selected) >= max_messages:
            break
        if used_chars + len(content) > max_chars and selected:
            break
        selected.append({"role": role, "content": content})
        used_chars += len(content)

    selected.reverse()
    prompt = system_prompt if system_prompt is not None else DEFAULT_SYSTEM_PROMPT
    return [{"role": "system", "content": prompt}, *selected]
