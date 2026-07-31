"""Health check endpoints."""

from fastapi import APIRouter

from config import settings
from models.schemas import HealthResponse
from services.llm_service import LLMService

router = APIRouter()
llm_service = LLMService()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    ollama_ok = await llm_service.is_available()
    return HealthResponse(
        status="healthy" if ollama_ok else "degraded",
        version=settings.app_version,
        ollama_reachable=ollama_ok,
    )
