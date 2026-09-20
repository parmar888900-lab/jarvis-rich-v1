"""Cloudflare Workers AI FLUX image provider."""

from __future__ import annotations

import base64
import uuid
from io import BytesIO
from pathlib import Path
from typing import Callable

import aiohttp
from PIL import Image

from backend.services.image_generation.base_provider import (
    BaseImageProvider,
)
from backend.services.image_generation.models import GeneratedImage
from backend.services.runtime.runtime_config import RuntimeConfig


class CloudflareFluxProvider(BaseImageProvider):
    """Generate images through Cloudflare Workers AI."""

    def __init__(
        self,
        runtime_config: RuntimeConfig | None = None,
        *,
        session_factory: Callable | None = None,
    ):
        config = (
            runtime_config
            if runtime_config is not None
            else RuntimeConfig.from_environment()
        )

        self.account_id = (
            config.cloudflare_account_id.strip()
        )

        self.api_token = (
            config.cloudflare_api_token.strip()
        )

        self.model = (
            config.cloudflare_flux_model.strip()
        )

        self.output_dir = (
            Path(config.generated_dir)
            / "images"
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.session_factory = (
            session_factory
            if session_factory is not None
            else aiohttp.ClientSession
        )

    @property
    def endpoint(self) -> str:
        return (
            "https://api.cloudflare.com/client/v4/"
            f"accounts/{self.account_id}/ai/run/"
            f"{self.model}"
        )

    def _validate_configuration(self) -> None:

        if not self.account_id:
            raise RuntimeError(
                "Cloudflare Account ID is not configured."
            )

        if not self.api_token:
            raise RuntimeError(
                "Cloudflare Workers AI API token "
                "is not configured."
            )

        if not self.model:
            raise RuntimeError(
                "Cloudflare FLUX model is not configured."
            )

    async def generate(
        self,
        prompt: str,
    ) -> GeneratedImage:

        if not isinstance(prompt, str):
            raise TypeError(
                "Image prompt must be a string."
            )

        prompt = prompt.strip()

        if not prompt:
            raise ValueError(
                "Image prompt cannot be empty."
            )

        self._validate_configuration()

        payload = {
            "prompt": prompt,
            "steps": 4,
        }

        headers = {
            "Authorization": (
                f"Bearer {self.api_token}"
            ),
            "Content-Type": "application/json",
        }

        async with self.session_factory() as session:

            async with session.post(
                self.endpoint,
                json=payload,
                headers=headers,
            ) as response:

                try:
                    data = await response.json()
                except Exception as exc:
                    text = await response.text()

                    raise RuntimeError(
                        "Cloudflare returned a "
                        "non-JSON response: "
                        f"{response.status} {text}"
                    ) from exc

                if response.status != 200:
                    raise RuntimeError(
                        "Cloudflare FLUX request failed: "
                        f"{response.status} {data}"
                    )

        image_base64 = self._extract_image(
            data
        )

        try:
            image_bytes = base64.b64decode(
                image_base64,
                validate=True,
            )
        except Exception as exc:
            raise RuntimeError(
                "Cloudflare returned invalid "
                "base64 image data."
            ) from exc

        if not image_bytes:
            raise RuntimeError(
                "Cloudflare returned an empty image."
            )

        output_path = (
            self.output_dir
            / f"jarvis_cf_{uuid.uuid4().hex}.jpg"
        )

        self._write_portrait_image(
            image_bytes=image_bytes,
            output_path=output_path,
        )

        return GeneratedImage(
            prompt=prompt,
            image_path=str(output_path),
            provider="flux-cloudflare",
            width=720,
            height=1280,
        )

    @staticmethod
    def _write_portrait_image(
        *,
        image_bytes: bytes,
        output_path: Path,
    ) -> None:
        """Normalize Cloudflare output to Jarvis portrait assets."""

        try:
            with Image.open(
                BytesIO(image_bytes)
            ) as source:

                image = source.convert(
                    "RGB"
                )

                width, height = image.size

                if width <= 0 or height <= 0:
                    raise RuntimeError(
                        "Cloudflare returned invalid "
                        "image dimensions."
                    )

                target_ratio = 9 / 16
                source_ratio = width / height

                if source_ratio > target_ratio:
                    crop_width = max(
                        1,
                        round(
                            height
                            * target_ratio
                        ),
                    )

                    left = max(
                        0,
                        (width - crop_width) // 2,
                    )

                    right = min(
                        width,
                        left + crop_width,
                    )

                    image = image.crop(
                        (
                            left,
                            0,
                            right,
                            height,
                        )
                    )

                elif source_ratio < target_ratio:
                    crop_height = max(
                        1,
                        round(
                            width
                            / target_ratio
                        ),
                    )

                    top = max(
                        0,
                        (height - crop_height) // 2,
                    )

                    bottom = min(
                        height,
                        top + crop_height,
                    )

                    image = image.crop(
                        (
                            0,
                            top,
                            width,
                            bottom,
                        )
                    )

                image = image.resize(
                    (720, 1280),
                    Image.Resampling.LANCZOS,
                )

                image.save(
                    output_path,
                    format="JPEG",
                    quality=95,
                    optimize=True,
                )

        except RuntimeError:
            raise

        except Exception as exc:
            raise RuntimeError(
                "Cloudflare returned image data "
                "that could not be processed."
            ) from exc

    @staticmethod
    def _extract_image(
        data: dict,
    ) -> str:

        if not isinstance(data, dict):
            raise RuntimeError(
                "Cloudflare returned an invalid response."
            )

        result = data.get("result")

        if not isinstance(result, dict):
            raise RuntimeError(
                "Cloudflare response has no valid result."
            )

        image = result.get("image")

        if not isinstance(image, str) or not image:
            raise RuntimeError(
                "Cloudflare response contained no image."
            )

        return image
