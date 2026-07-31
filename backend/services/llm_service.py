"""Local LLM integration via Ollama (free, open-source)."""

import httpx

from config import settings


class LLMService:
    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.default_model = settings.ollama_model

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def chat(self, messages: list[dict[str, str]], model: str | None = None) -> str:
        model = model or self.default_model

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={"model": model, "messages": messages, "stream": False},
                )
                response.raise_for_status()
                data = response.json()
                return data.get("message", {}).get("content", "No response from model.")
        except httpx.HTTPError as exc:
            return (
                f"Ollama is not reachable at {self.base_url}. "
                f"Install Ollama locally and run `ollama pull {model}`. Error: {exc}"
            )
