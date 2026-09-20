"""Portable LLM integration for Jarvis."""

from __future__ import annotations

import json

import httpx

from backend.services.runtime.runtime_config import (
    RuntimeConfig,
)


class LLMService:
    """Route Jarvis LLM requests to the selected provider."""

    OLLAMA_ALIASES = {
        "ollama",
        "local",
    }

    CLOUDFLARE_ALIASES = {
        "cloudflare",
        "workers-ai",
        "workers_ai",
    }

    def __init__(
        self,
        runtime_config: RuntimeConfig | None = None,
    ) -> None:

        self.config = (
            runtime_config
            if runtime_config is not None
            else RuntimeConfig.from_environment()
        )

        self.provider = (
            self.config.llm_provider
            .strip()
            .lower()
        )

        if self.provider in self.OLLAMA_ALIASES:
            self.provider = "ollama"

        elif self.provider in self.CLOUDFLARE_ALIASES:
            self.provider = "cloudflare"

        else:
            raise ValueError(
                "Unsupported LLM provider: "
                f"{self.config.llm_provider}"
            )

        # Preserve these attributes for callers/tests that
        # may inspect the old LLMService surface.
        self.base_url = (
            self.config.ollama_base_url.rstrip("/")
        )

        self.default_model = (
            self.config.ollama_model
            if self.provider == "ollama"
            else self.config.cloudflare_llm_model
        )

    async def is_available(
        self,
    ) -> bool:

        if self.provider == "ollama":
            return await self._ollama_available()

        return await self._cloudflare_available()

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        json_mode: bool = False,
    ) -> str:

        if self.provider == "ollama":
            return await self._chat_ollama(
                messages=messages,
                model=model,
                json_mode=json_mode,
            )

        return await self._chat_cloudflare(
            messages=messages,
            model=model,
            json_mode=json_mode,
        )

    async def _ollama_available(
        self,
    ) -> bool:

        try:
            async with httpx.AsyncClient(
                timeout=5
            ) as client:

                response = await client.get(
                    f"{self.base_url}/api/tags"
                )

                return (
                    response.status_code == 200
                )

        except Exception:
            return False

    async def _cloudflare_available(
        self,
    ) -> bool:

        if not self._cloudflare_configured():
            return False

        # A tiny inference request verifies credentials,
        # model availability, and Workers AI itself.
        try:
            await self._chat_cloudflare(
                messages=[
                    {
                        "role": "user",
                        "content": "Reply with OK.",
                    }
                ],
                json_mode=False,
            )

            return True

        except Exception:
            return False

    async def _chat_ollama(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None,
        json_mode: bool,
    ) -> str:

        selected_model = (
            model
            or self.config.ollama_model
        )

        prompt = "\n".join(
            f"{message['role'].upper()}: "
            f"{message['content']}"
            for message in messages
        )

        url = (
            f"{self.base_url}/api/generate"
        )

        payload = {
            "model": selected_model,
            "prompt": prompt,
            "stream": False,
        }

        if json_mode:
            payload["format"] = "json"

        async with httpx.AsyncClient(
            timeout=300
        ) as client:

            response = await client.post(
                url,
                json=payload,
            )

            response.raise_for_status()

            data = response.json()

        return str(
            data.get(
                "response",
                "",
            )
        )

    async def _chat_cloudflare(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None = None,
        json_mode: bool,
    ) -> str:

        if not self._cloudflare_configured():
            raise RuntimeError(
                "Cloudflare LLM credentials "
                "are not configured."
            )

        selected_model = (
            model
            or self.config.cloudflare_llm_model
        ).strip()

        if not selected_model:
            raise RuntimeError(
                "Cloudflare LLM model "
                "is not configured."
            )

        account_id = (
            self.config.cloudflare_account_id
            .strip()
        )

        token = (
            self.config.cloudflare_api_token
            .strip()
        )

        url = (
            "https://api.cloudflare.com/client/v4/"
            f"accounts/{account_id}/ai/run/"
            f"{selected_model}"
        )

        payload: dict = {
            "messages": messages,
        }

        if json_mode:
            payload["response_format"] = {
                "type": "json_object",
            }

        headers = {
            "Authorization": (
                f"Bearer {token}"
            ),
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(
            timeout=300
        ) as client:

            response = await client.post(
                url,
                headers=headers,
                json=payload,
            )

            response.raise_for_status()

            data = response.json()

        return self._extract_cloudflare_text(
            data
        )

    def _cloudflare_configured(
        self,
    ) -> bool:

        return bool(
            self.config.cloudflare_account_id.strip()
            and self.config.cloudflare_api_token.strip()
            and self.config.cloudflare_llm_model.strip()
        )

    @staticmethod
    def _extract_cloudflare_text(
        data: dict,
    ) -> str:

        if not isinstance(
            data,
            dict,
        ):
            raise RuntimeError(
                "Cloudflare LLM response "
                "is not a JSON object."
            )

        if data.get("success") is False:
            raise RuntimeError(
                "Cloudflare LLM request "
                "reported failure."
            )

        result = data.get(
            "result"
        )

        if isinstance(
            result,
            str,
        ):
            if result.strip():
                return result

        if isinstance(
            result,
            dict,
        ):
            response = result.get(
                "response"
            )

            if isinstance(
                response,
                str,
            ) and response.strip():
                return response

            # Cloudflare JSON Mode may return the
            # structured response as an actual JSON
            # value rather than encoded JSON text.
            # Preserve LLMService.chat()'s historical
            # string-return contract for Jarvis callers.
            if isinstance(
                response,
                (dict, list),
            ):
                return json.dumps(
                    response,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )

        raise RuntimeError(
            "Cloudflare LLM response "
            "contains no generated text."
        )
