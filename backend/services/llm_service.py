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
                response = await client.get(
                    f"{self.base_url}/api/tags"
                )
                return response.status_code == 200
        except Exception:
            return False

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        json_mode: bool = False,
    ) -> str:

        model = model or self.default_model

        prompt = "\n".join(
            f"{message['role'].upper()}: {message['content']}"
            for message in messages
        )

        url = f"{self.base_url}/api/generate"

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }

        if json_mode:
            payload["format"] = "json"

        print("\n========== LLM DEBUG ==========")
        print(f"BASE URL    : {self.base_url}")
        print(f"REQUEST URL : {url}")
        print(f"MODEL       : {model}")
        print(f"JSON MODE   : {json_mode}")
        print("================================\n")

        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                url,
                json=payload,
            )

            print("\n========== HTTP RESPONSE ==========")
            print(f"STATUS : {response.status_code}")
            print(response.text)
            print("===================================\n")

            response.raise_for_status()

            data = response.json()

            raw_response = data.get(
                "response",
                "",
            )

            print("\n========== RAW LLM RESPONSE ==========")
            print(raw_response)
            print("======================================\n")

            return raw_response
