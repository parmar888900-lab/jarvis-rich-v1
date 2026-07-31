"""Application configuration loaded from environment and config files."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "configs"
DATABASE_DIR = ROOT_DIR / "database"
LOGS_DIR = ROOT_DIR / "logs"

DATABASE_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(CONFIG_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "JARVIS AI"
    app_version: str = "0.1.0"
    debug: bool = True

    # Database (SQLite - local only)
    database_url: str = f"sqlite+aiosqlite:///{DATABASE_DIR / 'jarvis.db'}"

    # Local LLM via Ollama (free, open-source, runs locally)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000


settings = Settings()
