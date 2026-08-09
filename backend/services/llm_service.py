"""Local LLM integration via Ollama."""

import httpx

from backend.config import settings


class LLMService:
    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.default_model = settings.ollama_model

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    async def chat(self, messages: list[dict[str, str]], model: str | None = None) -> str:
        model = model or self.default_model

        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                },
            )

            response.raise_for_status()

            data = response.json()

            print("\n========== RAW LLM RESPONSE ==========\n")
            print(data["message"]["content"])
            print("\n======================================\n")

            return data["message"]["content"]