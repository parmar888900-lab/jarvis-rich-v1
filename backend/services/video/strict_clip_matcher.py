"""Strict positive/negative semantic clip matching for Rich V1."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import csv
import io
import shutil
import subprocess

import open_clip
import torch
from PIL import Image

from backend.services.video.source_clip_indexer import (
    IndexedSourceClip,
)
from backend.services.video.visual_beat_source_planner import (
    SourceVisualBeat,
)


@dataclass(slots=True)
class StrictMatchedClip:
    beat_id: str
    visual_goal: str

    clip_id: str
    source_path: str
    source_name: str

    start_time: float
    end_time: float
    duration: float

    preview_path: str

    positive_score: float
    negative_score: float
    final_score: float
    presentation_mode: str = "cover"

    def to_dict(self) -> dict:
        return asdict(self)


class StrictClipMatcher:
    """
    Match source clips against a concrete visual goal while penalizing
    footage resembling explicitly unwanted visuals.
    """

    MODEL_NAME = "ViT-B-32"
    PRETRAINED = "laion2b_s34b_b79k"

    ########################################################
    # Stricter than the earlier generic matcher.
    ########################################################

    MIN_POSITIVE_SCORE = 0.20
    MIN_FINAL_SCORE = 0.10

    NEGATIVE_WEIGHT = 0.55

    # Semantic similarity cannot rescue an almost-empty frame.  NASA and
    # archive documentaries often contain black title cards or pillarboxed
    # inserts that CLIP still associates with the narrated topic.  Those
    # frames are technically relevant but viewer-facing failures in a Short.
    DARK_LUMA_THRESHOLD = 18
    MIN_VISIBLE_PIXEL_FRACTION = 0.22

    ANNOTATION_MIN_CONFIDENCE = 45.0
    ANNOTATION_EDGE_BAND_FRACTION = 0.35

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

        self.image_cache: dict[
            str,
            torch.Tensor,
        ] = {}

    def match_many(
        self,
        *,
        beats: list[SourceVisualBeat],
        clips: list[IndexedSourceClip],
        max_reuse_per_source: int = 10,
    ) -> list[StrictMatchedClip]:

        if not beats or not clips:
            return []

        self._ensure_model()

        valid_clips = []
        embeddings = []

        for clip in clips:

            if not self._preview_has_usable_visual_density(
                clip.preview_path
            ):
                continue

            embedding = (
                self._image_embedding(
                    clip.preview_path
                )
            )

            if embedding is None:
                continue

            valid_clips.append(
                clip
            )

            embeddings.append(
                embedding
            )

        if not valid_clips:
            return []

        image_matrix = torch.cat(
            embeddings,
            dim=0,
        )

        used_clip_ids: set[str] = set()

        source_usage: dict[
            str,
            int,
        ] = {}

        output = []

        for beat in beats:

            positive_prompts = [
                beat.visual_goal,
                *beat.search_queries,
            ]

            positive_embedding = (
                self._text_embedding(
                    positive_prompts
                )
            )

            positive_scores = (
                positive_embedding
                @ image_matrix.T
            ).squeeze(0)

            negative_scores = torch.zeros_like(
                positive_scores
            )

            if beat.negative_visuals:

                negative_embedding = (
                    self._text_embedding(
                        beat.negative_visuals
                    )
                )

                negative_scores = (
                    negative_embedding
                    @ image_matrix.T
                ).squeeze(0)

            final_scores = (
                positive_scores
                - (
                    negative_scores
                    * self.NEGATIVE_WEIGHT
                )
            )

            ranked = torch.argsort(
                final_scores,
                descending=True,
            ).tolist()

            winner = None

            for index in ranked:

                clip = valid_clips[
                    index
                ]

                positive = float(
                    positive_scores[
                        index
                    ].item()
                )

                negative = float(
                    negative_scores[
                        index
                    ].item()
                )

                final = float(
                    final_scores[
                        index
                    ].item()
                )

                if (
                    positive
                    < self.MIN_POSITIVE_SCORE
                ):
                    continue

                if (
                    final
                    < self.MIN_FINAL_SCORE
                ):
                    continue

                if (
                    clip.clip_id
                    in used_clip_ids
                ):
                    continue

                if (
                    source_usage.get(
                        clip.source_path,
                        0,
                    )
                    >= max_reuse_per_source
                ):
                    continue

                winner = (
                    clip,
                    positive,
                    negative,
                    final,
                )

                break

            if winner is None:
                continue

            clip, positive, negative, final = (
                winner
            )

            used_clip_ids.add(
                clip.clip_id
            )

            source_usage[
                clip.source_path
            ] = (
                source_usage.get(
                    clip.source_path,
                    0,
                )
                + 1
            )

            output.append(
                StrictMatchedClip(
                    beat_id=beat.beat_id,
                    visual_goal=(
                        beat.visual_goal
                    ),
                    clip_id=(
                        clip.clip_id
                    ),
                    source_path=(
                        clip.source_path
                    ),
                    source_name=(
                        clip.source_name
                    ),
                    start_time=(
                        clip.start_time
                    ),
                    end_time=(
                        clip.end_time
                    ),
                    duration=(
                        clip.duration
                    ),
                    preview_path=(
                        clip.preview_path
                    ),
                    positive_score=round(
                        positive,
                        4,
                    ),
                    negative_score=round(
                        negative,
                        4,
                    ),
                    final_score=round(
                        final,
                        4,
                    ),
                    presentation_mode=(
                        self._preview_presentation_mode(
                            clip.preview_path
                        )
                    ),
                )
            )

        return output

    @classmethod
    def _preview_has_usable_visual_density(
        cls,
        path_value: str,
    ) -> bool:
        """Reject near-empty title cards before semantic matching."""

        path = Path(path_value)

        if not path.exists():
            return False

        try:
            with Image.open(path) as source:
                grayscale = source.convert("L")
                histogram = grayscale.histogram()

            total_pixels = sum(histogram)

            if total_pixels <= 0:
                return False

            dark_pixels = sum(
                histogram[
                    : cls.DARK_LUMA_THRESHOLD + 1
                ]
            )

            visible_fraction = (
                1.0
                - dark_pixels / total_pixels
            )

            return (
                visible_fraction
                >= cls.MIN_VISIBLE_PIXEL_FRACTION
            )

        except Exception:
            return False

    @classmethod
    def _annotation_risk_from_tsv(
        cls,
        tsv_text: str,
        *,
        width: int,
        height: int,
    ) -> bool:
        """Detect readable source text near crop-sensitive frame edges."""

        if width <= 0 or height <= 0:
            return False

        words = []
        try:
            rows = csv.DictReader(
                io.StringIO(str(tsv_text or "")),
                delimiter="\t",
            )
            for row in rows:
                text = str(row.get("text", "")).strip()
                if len("".join(c for c in text if c.isalnum())) < 2:
                    continue
                try:
                    confidence = float(row.get("conf", "-1"))
                    top = int(row.get("top", "0"))
                    box_height = int(row.get("height", "0"))
                except (TypeError, ValueError):
                    continue
                if confidence < cls.ANNOTATION_MIN_CONFIDENCE:
                    continue
                center_y = top + box_height / 2.0
                words.append(center_y)
        except Exception:
            return False

        if len(words) < 2:
            return False

        upper_limit = height * cls.ANNOTATION_EDGE_BAND_FRACTION
        lower_limit = height * (1.0 - cls.ANNOTATION_EDGE_BAND_FRACTION)
        edge_words = sum(
            1
            for center_y in words
            if center_y <= upper_limit or center_y >= lower_limit
        )
        return edge_words >= 2

    @classmethod
    def _preview_presentation_mode(cls, path_value: str) -> str:
        """Choose context-safe framing when OCR finds edge annotations.

        Tesseract is optional. Missing OCR capability preserves the existing
        cover behavior instead of blocking production.
        """

        executable = shutil.which("tesseract")
        path = Path(path_value)
        if not executable or not path.exists():
            return "cover"

        try:
            with Image.open(path) as source:
                width, height = source.size

            completed = subprocess.run(
                [
                    executable,
                    str(path),
                    "stdout",
                    "--psm",
                    "11",
                    "tsv",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=12,
            )
            if completed.returncode != 0:
                return "cover"

            if cls._annotation_risk_from_tsv(
                completed.stdout,
                width=width,
                height=height,
            ):
                return "contain_safe_area"
        except Exception:
            return "cover"

        return "cover"

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
        path_value: str,
    ) -> torch.Tensor | None:

        cached = self.image_cache.get(
            path_value
        )

        if cached is not None:
            return cached

        path = Path(
            path_value
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

            features = (
                features.cpu()
            )

            self.image_cache[
                path_value
            ] = features

            return features

        except Exception:
            return None

    def _text_embedding(
        self,
        prompts: list[str],
    ) -> torch.Tensor:

        cleaned = [
            " ".join(
                str(prompt).split()
            ).strip()
            for prompt in prompts
            if str(prompt).strip()
        ]

        if not cleaned:
            raise ValueError(
                "Text embedding requires prompts."
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

            ################################################
            # Average all positive or negative descriptions.
            ################################################

            features = features.mean(
                dim=0,
                keepdim=True,
            )

            features = (
                features
                / features.norm(
                    dim=-1,
                    keepdim=True,
                )
            )

        return features.cpu()
