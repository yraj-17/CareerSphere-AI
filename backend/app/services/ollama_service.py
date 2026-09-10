from ollama import AsyncClient
from app.core.config import settings


client = AsyncClient(host=settings.OLLAMA_BASE_URL)


async def generate_response(
    prompt: str,
    system_prompt: str | None = None,
    think: bool = False,
) -> str:

    messages = []

    if system_prompt:
        messages.append({
            "role": "system",
            "content": system_prompt,
        })

    messages.append({
        "role": "user",
        "content": prompt,
    })

    response = await client.chat(
        model=settings.OLLAMA_MODEL,
        messages=messages,
        think=think,
    )

    return response["message"]["content"]