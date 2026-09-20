import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import httpx

from backend.services.llm_service import (
    LLMService,
)
from backend.services.runtime.runtime_config import (
    RuntimeConfig,
)


def make_config(
    root: Path,
    provider: str,
) -> RuntimeConfig:

    return RuntimeConfig(
        ollama_base_url="http://ollama:11434",
        ollama_model="qwen2.5:7b",
        comfyui_url="http://comfyui:8188",
        comfyui_output_dir=root,
        flux_workflow_path=root / "workflow.json",
        piper_executable=root / "piper",
        piper_model_path=root / "voice.onnx",
        ffmpeg_executable="ffmpeg",
        generated_dir=root,
        database_url="",
        youtube_token_path=root / "token.json",
        youtube_client_secret_path=root / "secret.json",
        image_provider="comfyui",
        cloudflare_account_id="account-123",
        cloudflare_api_token="token-456",
        cloudflare_flux_model=(
            "@cf/black-forest-labs/"
            "flux-1-schnell"
        ),
        llm_provider=provider,
        cloudflare_llm_model=(
            "@cf/meta/"
            "llama-3.1-8b-instruct-fast"
        ),
    )


async def test_ollama_contract():

    with tempfile.TemporaryDirectory() as temp:

        config = make_config(
            Path(temp),
            "ollama",
        )

        service = LLMService(config)

        request_seen = {}

        async def handler(request):
            request_seen["url"] = str(
                request.url
            )

            request_seen["payload"] = (
                json.loads(
                    request.content.decode()
                )
            )

            return httpx.Response(
                200,
                json={
                    "response":
                        '{"title":"ok"}'
                },
            )

        transport = httpx.MockTransport(
            handler
        )

        real_client = httpx.AsyncClient

        def client_factory(*args, **kwargs):
            kwargs["transport"] = transport
            return real_client(
                *args,
                **kwargs,
            )

        with patch(
            "backend.services.llm_service."
            "httpx.AsyncClient",
            side_effect=client_factory,
        ):
            result = await service.chat(
                [
                    {
                        "role": "user",
                        "content": "hello",
                    }
                ],
                json_mode=True,
            )

        assert result == '{"title":"ok"}'

        assert request_seen[
            "url"
        ].endswith(
            "/api/generate"
        )

        assert request_seen[
            "payload"
        ]["format"] == "json"

        assert request_seen[
            "payload"
        ]["options"]["num_ctx"] == 8192

        print(
            "PASS: Ollama chat contract preserved."
        )


async def test_cloudflare_contract():

    with tempfile.TemporaryDirectory() as temp:

        config = make_config(
            Path(temp),
            "cloudflare",
        )

        service = LLMService(config)

        request_seen = {}

        async def handler(request):

            request_seen["url"] = str(
                request.url
            )

            request_seen["auth"] = (
                request.headers.get(
                    "Authorization"
                )
            )

            request_seen["payload"] = (
                json.loads(
                    request.content.decode()
                )
            )

            return httpx.Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "response":
                            '{"title":"cloud"}'
                    },
                },
            )

        transport = httpx.MockTransport(
            handler
        )

        real_client = httpx.AsyncClient

        def client_factory(*args, **kwargs):
            kwargs["transport"] = transport
            return real_client(
                *args,
                **kwargs,
            )

        with patch(
            "backend.services.llm_service."
            "httpx.AsyncClient",
            side_effect=client_factory,
        ):
            result = await service.chat(
                [
                    {
                        "role": "system",
                        "content": "Return JSON.",
                    },
                    {
                        "role": "user",
                        "content": "hello",
                    },
                ],
                json_mode=True,
            )

        assert result == (
            '{"title":"cloud"}'
        )

        assert (
            "/ai/run/"
            "@cf/meta/"
            "llama-3.1-8b-instruct-fast"
            in request_seen["url"]
        )

        assert request_seen["auth"] == (
            "Bearer token-456"
        )

        payload = request_seen[
            "payload"
        ]

        assert (
            payload["messages"][0]["role"]
            == "system"
        )

        assert payload[
            "response_format"
        ] == {
            "type": "json_object"
        }

        print(
            "PASS: Cloudflare chat "
            "request contract."
        )


async def test_cloudflare_structured_json_response():

    with tempfile.TemporaryDirectory() as temp:

        config = make_config(
            Path(temp),
            "cloudflare",
        )

        service = LLMService(config)

        async def handler(request):

            return httpx.Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "response": {
                            "status": "ok",
                            "provider": "cloudflare",
                        }
                    },
                },
            )

        transport = httpx.MockTransport(
            handler
        )

        real_client = httpx.AsyncClient

        def client_factory(*args, **kwargs):
            kwargs["transport"] = transport
            return real_client(
                *args,
                **kwargs,
            )

        with patch(
            "backend.services.llm_service."
            "httpx.AsyncClient",
            side_effect=client_factory,
        ):
            result = await service.chat(
                [
                    {
                        "role": "user",
                        "content": "Return JSON.",
                    }
                ],
                json_mode=True,
            )

        parsed = json.loads(result)

        assert parsed == {
            "status": "ok",
            "provider": "cloudflare",
        }

        assert isinstance(
            result,
            str,
        )

        print(
            "PASS: Cloudflare structured JSON "
            "is normalized to Jarvis string contract."
        )


async def test_missing_credentials():

    with tempfile.TemporaryDirectory() as temp:

        config = make_config(
            Path(temp),
            "cloudflare",
        )

        config = RuntimeConfig(
            **{
                **config.__dict__,
                "cloudflare_api_token": "",
            }
        )

        service = LLMService(config)

        try:
            await service.chat(
                [
                    {
                        "role": "user",
                        "content": "hello",
                    }
                ]
            )

        except RuntimeError as exc:
            assert (
                "credentials"
                in str(exc).lower()
            )

        else:
            raise AssertionError(
                "Missing credentials "
                "did not fail closed."
            )

        assert not await service.is_available()

        print(
            "PASS: missing Cloudflare "
            "credentials fail closed."
        )


def test_unknown_provider():

    with tempfile.TemporaryDirectory() as temp:

        config = make_config(
            Path(temp),
            "unknown",
        )

        try:
            LLMService(config)

        except ValueError as exc:
            assert (
                "unsupported llm provider"
                in str(exc).lower()
            )

        else:
            raise AssertionError(
                "Unknown LLM provider "
                "did not fail closed."
            )

        print(
            "PASS: unknown LLM provider "
            "fails closed."
        )


async def main():

    await test_ollama_contract()
    await test_cloudflare_contract()
    await test_cloudflare_structured_json_response()
    await test_missing_credentials()
    test_unknown_provider()

    print(
        "\nPASS: LLM provider routing "
        "regression suite complete."
    )


if __name__ == "__main__":
    asyncio.run(main())
