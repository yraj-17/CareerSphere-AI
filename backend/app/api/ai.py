from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.ollama_service import generate_response


router = APIRouter(
    prefix="/ai",
    tags=["AI"],
)


class AIRequest(BaseModel):
    prompt: str
    think: bool = False


class AIResponse(BaseModel):
    response: str


@router.post("/chat", response_model=AIResponse)
async def chat_with_ai(request: AIRequest):

    if not request.prompt.strip():
        raise HTTPException(
            status_code=400,
            detail="Prompt cannot be empty.",
        )

    try:
        response = await generate_response(
            prompt=request.prompt,
            think=request.think,
        )

        return AIResponse(response=response)

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"AI service unavailable: {str(exc)}",
        )