"""Settings endpoints."""

from fastapi import APIRouter

from config import settings
from models.schemas import SettingsResponse, SettingsUpdate

router = APIRouter()


@router.get("/", response_model=SettingsResponse)
async def get_settings():
    return SettingsResponse(
        app_name=settings.app_name,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
        debug=settings.debug,
    )


@router.patch("/", response_model=SettingsResponse)
async def update_settings(payload: SettingsUpdate):
    if payload.ollama_base_url is not None:
        settings.ollama_base_url = payload.ollama_base_url
    if payload.ollama_model is not None:
        settings.ollama_model = payload.ollama_model
    if payload.debug is not None:
        settings.debug = payload.debug

    return SettingsResponse(
        app_name=settings.app_name,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
        debug=settings.debug,
    )
