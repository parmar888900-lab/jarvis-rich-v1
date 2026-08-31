import asyncio
import base64
import tempfile
from io import BytesIO
from pathlib import Path

from PIL import Image

from backend.services.image_generation.cloudflare_flux_provider import (
    CloudflareFluxProvider,
)
from backend.services.runtime.runtime_config import RuntimeConfig


def make_square_jpeg() -> bytes:

    buffer = BytesIO()

    image = Image.new(
        "RGB",
        (1024, 1024),
        (120, 130, 140),
    )

    image.save(
        buffer,
        format="JPEG",
        quality=90,
    )

    return buffer.getvalue()


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
            make_square_jpeg()
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
        assert image.width == 720
        assert image.height == 1280

        output = Path(
            image.image_path
        )

        assert output.exists()
        assert output.suffix.lower() == ".jpg"

        with Image.open(output) as saved:
            assert saved.size == (
                720,
                1280,
            )
            assert saved.format == "JPEG"

        calls = factory.session.calls

        assert len(calls) == 1

        call = calls[0]

        assert (
            call["json"]["prompt"]
            == "Jarvis provider test"
        )

        assert call["json"]["steps"] == 4

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
            "PASS: square provider output normalized "
            "to 720x1280 portrait JPEG."
        )

        print(
            "PASS: GeneratedImage dimensions "
            "match persisted image."
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


async def test_invalid_image_bytes():

    with tempfile.TemporaryDirectory() as temp:

        root = Path(temp)

        encoded = base64.b64encode(
            b"not-an-image"
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

        try:
            await provider.generate(
                "test"
            )
        except RuntimeError as exc:
            assert (
                "could not be processed"
                in str(exc).lower()
            )
        else:
            raise AssertionError(
                "Invalid image bytes "
                "did not fail closed."
            )

        print(
            "PASS: invalid decoded image "
            "fails closed."
        )


async def main():

    await test_success()
    await test_missing_credentials()
    await test_bad_response()
    await test_invalid_image_bytes()

    print(
        "\nPASS: Cloudflare FLUX provider "
        "regression suite complete."
    )


if __name__ == "__main__":
    asyncio.run(main())
