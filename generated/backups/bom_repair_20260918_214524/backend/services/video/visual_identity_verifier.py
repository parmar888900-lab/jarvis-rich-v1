"""Hard visual identity verification for Jarvis Rich V1."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import open_clip
import torch
from PIL import Image


@dataclass(slots=True)
class IdentityVerificationResult:
    valid: bool
    positive_score: float
    negative_score: float
    margin: float
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


class VisualIdentityVerifier:
    """
    Verify that the required subject/object is actually present.

    This is intentionally stricter than generic semantic similarity.
    """

    MODEL_NAME = "ViT-B-32"
    PRETRAINED = "laion2b_s34b_b79k"

    MIN_POSITIVE = 0.22
    MIN_MARGIN = 0.035

    def __init__(
        self,
        *,
        device: str | None = None,
    ) -> None:

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

        self._image_cache = {}

    def verify(
        self,
        *,
        image_path: str,
        required_prompts: list[str],
        reject_prompts: list[str],
    ) -> IdentityVerificationResult:

        self._ensure_model()

        image_embedding = (
            self._image_embedding(
                image_path
            )
        )

        if image_embedding is None:
            return IdentityVerificationResult(
                valid=False,
                positive_score=0.0,
                negative_score=0.0,
                margin=0.0,
                reason="image_unavailable",
            )

        positive_embedding = (
            self._text_embedding(
                required_prompts
            )
        )

        positive_score = float(
            (
                image_embedding
                @ positive_embedding.T
            ).max().item()
        )

        negative_score = 0.0

        if reject_prompts:

            negative_embedding = (
                self._text_embedding(
                    reject_prompts
                )
            )

            negative_score = float(
                (
                    image_embedding
                    @ negative_embedding.T
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
            reason = (
                "required_visual_present"
            )

        elif (
            positive_score
            < self.MIN_POSITIVE
        ):
            reason = (
                "required_visual_not_detected"
            )

        else:
            reason = (
                "distractor_similarity_too_high"
            )

        return IdentityVerificationResult(
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

    def _image_embedding(
        self,
        image_path: str,
    ):

        cached = self._image_cache.get(
            image_path
        )

        if cached is not None:
            return cached

        path = Path(
            image_path
        )

        if not path.exists():
            return None

        try:

            image = Image.open(
                path
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

                features = (
                    self.model.encode_image(
                        tensor
                    )
                )

                features = (
                    features
                    / features.norm(
                        dim=-1,
                        keepdim=True,
                    )
                )

            features = features.cpu()

            self._image_cache[
                image_path
            ] = features

            return features

        except Exception:
            return None

    def _text_embedding(
        self,
        prompts: list[str],
    ):

        cleaned = [
            " ".join(
                str(item).split()
            ).strip()
            for item in prompts
            if str(item).strip()
        ]

        if not cleaned:
            raise ValueError(
                "Identity verification requires prompts."
            )

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

        return features.cpu()
