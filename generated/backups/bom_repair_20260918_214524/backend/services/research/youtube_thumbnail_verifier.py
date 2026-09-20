"""Thumbnail visual verification for YouTube discovery candidates."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path

import open_clip
import requests
import torch
from PIL import Image


@dataclass(slots=True)
class ThumbnailVerification:
    valid: bool
    positive_score: float
    negative_score: float
    margin: float
    reason: str
    local_path: str

    def to_dict(self) -> dict:
        return asdict(self)


class YouTubeThumbnailVerifier:

    MODEL_NAME = "ViT-B-32"
    PRETRAINED = "laion2b_s34b_b79k"

    MIN_POSITIVE = 0.22
    MIN_MARGIN = 0.025

    def __init__(
        self,
        *,
        cache_dir: str | Path = (
            "generated/youtube_thumbnails"
        ),
        device: str | None = None,
    ) -> None:

        self.cache_dir = Path(
            cache_dir
        )

        self.cache_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.device = (
            device
            or (
                "cuda"
                if torch.cuda.is_available()
                else "cpu"
            )
        )

        self.model = None
        self.preprocess = None
        self.tokenizer = None

    def verify(
        self,
        *,
        thumbnail_url: str,
        positive_prompts: list[str],
        negative_prompts: list[str],
    ) -> ThumbnailVerification:

        image_path = self._download(
            thumbnail_url
        )

        if image_path is None:

            return ThumbnailVerification(
                valid=False,
                positive_score=0.0,
                negative_score=0.0,
                margin=0.0,
                reason="thumbnail_unavailable",
                local_path="",
            )

        self._ensure_model()

        image = Image.open(
            image_path
        ).convert(
            "RGB"
        )

        tensor = (
            self.preprocess(
                image
            )
            .unsqueeze(0)
            .to(
                self.device
            )
        )

        with torch.no_grad():

            image_features = (
                self.model.encode_image(
                    tensor
                )
            )

            image_features = (
                image_features
                / image_features.norm(
                    dim=-1,
                    keepdim=True,
                )
            )

            positive = self._text_features(
                positive_prompts
            )

            negative = self._text_features(
                negative_prompts
            )

            positive_score = float(
                (
                    image_features
                    @ positive.T
                ).max().item()
            )

            negative_score = float(
                (
                    image_features
                    @ negative.T
                ).max().item()
            )

        margin = (
            positive_score
            - negative_score
        )

        valid = (
            positive_score
            >= self.MIN_POSITIVE
            and margin
            >= self.MIN_MARGIN
        )

        if valid:
            reason = "product_visual"
        elif positive_score < self.MIN_POSITIVE:
            reason = "product_not_detected"
        else:
            reason = "talking_head_or_distractor"

        return ThumbnailVerification(
            valid=valid,
            positive_score=round(
                positive_score,
                4,
            ),
            negative_score=round(
                negative_score,
                4,
            ),
            margin=round(
                margin,
                4,
            ),
            reason=reason,
            local_path=str(
                image_path
            ),
        )

    def _ensure_model(
        self,
    ) -> None:

        if self.model is not None:
            return

        model, _, preprocess = (
            open_clip.create_model_and_transforms(
                self.MODEL_NAME,
                pretrained=self.PRETRAINED,
                device=self.device,
            )
        )

        tokenizer = (
            open_clip.get_tokenizer(
                self.MODEL_NAME
            )
        )

        model.eval()

        self.model = model
        self.preprocess = preprocess
        self.tokenizer = tokenizer

    def _text_features(
        self,
        prompts: list[str],
    ):

        cleaned = [
            str(item).strip()
            for item in prompts
            if str(item).strip()
        ]

        tokens = (
            self.tokenizer(
                cleaned
            )
            .to(
                self.device
            )
        )

        with torch.no_grad():

            features = (
                self.model.encode_text(
                    tokens
                )
            )

            features = (
                features
                / features.norm(
                    dim=-1,
                    keepdim=True,
                )
            )

        return features

    def _download(
        self,
        url: str,
    ) -> Path | None:

        if not url:
            return None

        digest = hashlib.sha1(
            url.encode(
                "utf-8"
            )
        ).hexdigest()[:16]

        output = (
            self.cache_dir
            / f"{digest}.jpg"
        )

        if (
            output.exists()
            and output.stat().st_size > 0
        ):
            return output

        try:

            response = requests.get(
                url,
                timeout=20,
            )

            response.raise_for_status()

            output.write_bytes(
                response.content
            )

        except Exception:
            return None

        return output
