"""Portable runtime configuration for Jarvis execution providers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _read_text(
    name: str,
    *,
    default: str,
) -> str:
    value = os.getenv(
        name
    )

    if value is None:
        value = default

    return str(
        value
    ).strip()


def _read_path(
    name: str,
    *,
    default: str | Path,
) -> Path:
    value = os.getenv(
        name
    )

    if value is None:
        value = str(
            default
        )

    return Path(
        value
    ).expanduser()


@dataclass(frozen=True)
class RuntimeConfig:
    """Machine-specific provider configuration."""

    ollama_base_url: str
    ollama_model: str

    comfyui_url: str
    comfyui_output_dir: Path
    flux_workflow_path: Path


    piper_executable: Path
    piper_model_path: Path

    ffmpeg_executable: str

    generated_dir: Path
    media_library_dir: Path
    database_url: str

    youtube_token_path: Path
    youtube_client_secret_path: Path

    # Optional cloud image provider configuration.
    # Defaults preserve compatibility with existing
    # RuntimeConfig(...) callers.
    image_provider: str = "comfyui"
    cloudflare_account_id: str = ""
    cloudflare_api_token: str = ""
    cloudflare_flux_model: str = (
        "@cf/black-forest-labs/"
        "flux-1-schnell"
    )

    # Optional cloud LLM provider configuration.
    # Ollama remains the development default.
    llm_provider: str = "ollama"
    cloudflare_llm_model: str = (
        "@cf/meta/"
        "llama-3.1-8b-instruct-fast"
    )

    @classmethod
    def from_environment(
        cls,
    ) -> "RuntimeConfig":
        """Build configuration without mutating application settings."""

        return cls(
            ollama_base_url=_read_text(
                "JARVIS_OLLAMA_BASE_URL",
                default="http://localhost:11434",
            ),
            ollama_model=_read_text(
                "JARVIS_OLLAMA_MODEL",
                default="qwen2.5:7b",
            ),
            comfyui_url=_read_text(
                "JARVIS_COMFYUI_URL",
                default="http://127.0.0.1:8188",
            ),
            comfyui_output_dir=_read_path(
                "JARVIS_COMFYUI_OUTPUT_DIR",
                default=(
                    r"C:\Users\hp\ComfyUI\output"
                ),
            ),
            flux_workflow_path=_read_path(
                "JARVIS_FLUX_WORKFLOW_PATH",
                default=(
                    "configs/workflows/"
                    "flux_api.json"
                ),
            ),
            image_provider=_read_text(
                "JARVIS_IMAGE_PROVIDER",
                default="comfyui",
            ),
            cloudflare_account_id=_read_text(
                "JARVIS_CLOUDFLARE_ACCOUNT_ID",
                default="",
            ),
            cloudflare_api_token=_read_text(
                "JARVIS_CLOUDFLARE_API_TOKEN",
                default="",
            ),
            cloudflare_flux_model=_read_text(
                "JARVIS_CLOUDFLARE_FLUX_MODEL",
                default=(
                    "@cf/black-forest-labs/"
                    "flux-1-schnell"
                ),
            ),
            llm_provider=_read_text(
                "JARVIS_LLM_PROVIDER",
                default="ollama",
            ),
            cloudflare_llm_model=_read_text(
                "JARVIS_CLOUDFLARE_LLM_MODEL",
                default=(
                    "@cf/meta/"
                    "llama-3.1-8b-instruct-fast"
                ),
            ),
            piper_executable=_read_path(
                "JARVIS_PIPER_EXECUTABLE",
                default=(
                    "venv/Scripts/piper.exe"
                ),
            ),
            piper_model_path=_read_path(
                "JARVIS_PIPER_MODEL_PATH",
                default=(
                    "models/piper/"
                    "en_GB-northern_english_"
                    "male-medium.onnx"
                ),
            ),
            ffmpeg_executable=_read_text(
                "JARVIS_FFMPEG_EXECUTABLE",
                default="ffmpeg",
            ),
            generated_dir=_read_path(
                "JARVIS_GENERATED_DIR",
                default="generated",
            ),
            media_library_dir=_read_path(
                "JARVIS_MEDIA_LIBRARY_DIR",
                default="media_library",
            ),
            database_url=_read_text(
                "JARVIS_DATABASE_URL",
                default="",
            ),
            youtube_token_path=_read_path(
                "JARVIS_YOUTUBE_TOKEN_PATH",
                default=(
                    "secrets/youtube_token.json"
                ),
            ),
            youtube_client_secret_path=_read_path(
                "JARVIS_YOUTUBE_CLIENT_SECRET_PATH",
                default=(
                    "secrets/"
                    "youtube_client_secret.json"
                ),
            ),
        )
