import asyncio
import base64
import tempfile
from pathlib import Path

from backend.services.image_generation.cloudflare_flux_provider import (
    CloudflareFluxProvider,
)
from backend.services.runtime.runtime_config import RuntimeConfig


PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"jarvis-cloudflare-provider-test"
)


class FakeResponse:

    def __init__(
        self,
        *,
        status=200,
        payload=None,
        text="",
    ):
        self.status = status
        self.payload = payload
        self.response_text = text

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False

    async def json(self):
        return self.payload

    async def text(self):
        return self.response_text


class FakeSession:

    def __init__(
        self,
        response,
    ):
        self.response = response
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False

    def post(
        self,
        url,
        *,
        json,
        headers,
    ):
        self.calls.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
            }
        )

        return self.response


class FakeSessionFactory:

    def __init__(
        self,
        response,
    ):
        self.session = FakeSession(
            response
        )

    def __call__(self):
        return self.session


def make_config(
    root: Path,
) -> RuntimeConfig:

    return RuntimeConfig(
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen2.5:7b",
        comfyui_url="http://127.0.0.1:8188",
        comfyui_output_dir=root / "comfy",
        flux_workflow_path=Path(
            "configs/workflows/flux_api.json"
        ),
        piper_executable=Path("piper"),
        piper_model_path=Path("voice.onnx"),
        ffmpeg_executable="ffmpeg",
        generated_dir=root,
        database_url="",
        youtube_token_path=Path("token.json"),
        youtube_client_secret_path=Path(
            "secret.json"
        ),
        image_provider="cloudflare",
        cloudflare_account_id="test-account",
        cloudflare_api_token="test-token",
        cloudflare_flux_model=(
            "@cf/black-forest-labs/"
            "flux-1-schnell"
        ),
    )


async def test_success():

    with tempfile.TemporaryDirectory() as temp:

        root = Path(temp)

        encoded = base64.b64encode(
            PNG_BYTES
        ).decode("ascii")

        response = FakeResponse(
            payload={
                "success": True,
                "result": {
                    "image": encoded,
                },
            }
        )

        factory = FakeSessionFactory(
            response
        )

        provider = CloudflareFluxProvider(
            runtime_config=make_config(root),
            session_factory=factory,
        )

        image = await provider.generate(
            "Jarvis provider test"
        )

        assert image.prompt == "Jarvis provider test"
        assert image.provider == "flux-cloudflare"
        assert image.width == 512
        assert image.height == 512

        output = Path(
            image.image_path
        )

        assert output.exists()
        assert output.read_bytes() == PNG_BYTES

        calls = factory.session.calls

        assert len(calls) == 1

        call = calls[0]

        assert (
            call["json"]["prompt"]
            == "Jarvis provider test"
        )

        assert call["json"]["num_steps"] == 4

        assert (
            call["headers"]["Authorization"]
            == "Bearer test-token"
        )

        assert (
            call["url"]
            ==
            "https://api.cloudflare.com/client/v4/"
            "accounts/test-account/ai/run/"
            "@cf/black-forest-labs/"
            "flux-1-schnell"
        )

        print(
            "PASS: Cloudflare request contract."
        )

        print(
            "PASS: Cloudflare image persisted."
        )


async def test_missing_credentials():

    with tempfile.TemporaryDirectory() as temp:

        root = Path(temp)

        config = make_config(
            root
        )

        config = RuntimeConfig(
            ollama_base_url=config.ollama_base_url,
            ollama_model=config.ollama_model,
            comfyui_url=config.comfyui_url,
            comfyui_output_dir=config.comfyui_output_dir,
            flux_workflow_path=config.flux_workflow_path,
            piper_executable=config.piper_executable,
            piper_model_path=config.piper_model_path,
            ffmpeg_executable=config.ffmpeg_executable,
            generated_dir=config.generated_dir,
            database_url=config.database_url,
            youtube_token_path=config.youtube_token_path,
            youtube_client_secret_path=(
                config.youtube_client_secret_path
            ),
            image_provider="cloudflare",
        )

        provider = CloudflareFluxProvider(
            runtime_config=config,
        )

        try:
            await provider.generate(
                "test"
            )
        except RuntimeError as exc:
            assert (
                "Account ID"
                in str(exc)
            )
        else:
            raise AssertionError(
                "Missing Cloudflare credentials "
                "did not fail closed."
            )

        print(
            "PASS: missing credentials fail closed."
        )


async def test_bad_response():

    with tempfile.TemporaryDirectory() as temp:

        root = Path(temp)

        response = FakeResponse(
            payload={
                "success": False,
                "errors": [
                    {
                        "message": "fake failure",
                    }
                ],
            },
        )

        factory = FakeSessionFactory(
            response
        )

        provider = CloudflareFluxProvider(
            runtime_config=make_config(root),
            session_factory=factory,
        )

        try:
            await provider.generate(
                "test"
            )
        except RuntimeError as exc:
            message = str(exc).lower()

            assert (
                "no image" in message
                or "no valid result" in message
            )
        else:
            raise AssertionError(
                "Missing result image "
                "did not fail closed."
            )

        print(
            "PASS: malformed provider result "
            "fails closed."
        )


async def main():

    await test_success()
    await test_missing_credentials()
    await test_bad_response()

    print(
        "\nPASS: Cloudflare FLUX provider "
        "regression suite complete."
    )


if __name__ == "__main__":
    asyncio.run(main())
