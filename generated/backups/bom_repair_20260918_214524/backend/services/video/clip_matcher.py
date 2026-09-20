"""Semantic clip matching for Jarvis Rich V1."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path

import torch
from PIL import Image
import open_clip

from backend.services.video.source_clip_indexer import (
    IndexedSourceClip,
)


@dataclass(slots=True)
class MatchedClip:
    beat_id: str
    query: str
    clip_id: str
    source_path: str
    source_name: str

    start_time: float
    end_time: float
    duration: float

    preview_path: str

    semantic_score: float

    def to_dict(self) -> dict:
        return asdict(self)


class ClipMatcher:
    """
    Match narration/visual beats to indexed source clips using CLIP.

    One image embedding is created for each indexed preview frame.
    Beat text is embedded and compared by cosine similarity.
    """

    MODEL_NAME = "ViT-B-32"
    PRETRAINED = "laion2b_s34b_b79k"

    MIN_SCORE = 0.18

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

        self._embedding_cache: dict[
            str,
            torch.Tensor,
        ] = {}

    def match_many(
        self,
        *,
        beats: list[dict],
        clips: list[IndexedSourceClip],
        max_reuse_per_source: int = 8,
    ) -> list[MatchedClip]:

        if not beats:
            return []

        if not clips:
            return []

        self._ensure_model()

        ####################################################
        # Precompute clip embeddings once.
        ####################################################

        clip_embeddings = []

        valid_clips = []

        for clip in clips:

            embedding = self._clip_embedding(
                clip
            )

            if embedding is None:
                continue

            valid_clips.append(
                clip
            )

            clip_embeddings.append(
                embedding
            )

        if not valid_clips:
            return []

        image_matrix = torch.cat(
            clip_embeddings,
            dim=0,
        )

        used_clip_ids: set[str] = set()

        source_usage: dict[
            str,
            int,
        ] = {}

        output: list[
            MatchedClip
        ] = []

        for beat in beats:

            beat_id = str(
                beat.get(
                    "beat_id",
                    "",
                )
            ).strip()

            query = " ".join(
                str(
                    beat.get(
                        "query",
                        "",
                    )
                ).split()
            ).strip()

            if not query:
                continue

            text_embedding = (
                self._text_embedding(
                    query
                )
            )

            similarities = (
                text_embedding
                @ image_matrix.T
            ).squeeze(0)

            ranked_indexes = torch.argsort(
                similarities,
                descending=True,
            ).tolist()

            selected = None
            selected_score = 0.0

            for index in ranked_indexes:

                clip = valid_clips[
                    index
                ]

                score = float(
                    similarities[
                        index
                    ].item()
                )

                if score < self.MIN_SCORE:
                    break

                if (
                    clip.clip_id
                    in used_clip_ids
                ):
                    continue

                source_key = (
                    clip.source_path
                )

                if (
                    source_usage.get(
                        source_key,
                        0,
                    )
                    >= max_reuse_per_source
                ):
                    continue

                selected = clip
                selected_score = score
                break

            if selected is None:
                continue

            used_clip_ids.add(
                selected.clip_id
            )

            source_usage[
                selected.source_path
            ] = (
                source_usage.get(
                    selected.source_path,
                    0,
                )
                + 1
            )

            output.append(
                MatchedClip(
                    beat_id=beat_id,
                    query=query,
                    clip_id=(
                        selected.clip_id
                    ),
                    source_path=(
                        selected.source_path
                    ),
                    source_name=(
                        selected.source_name
                    ),
                    start_time=(
                        selected.start_time
                    ),
                    end_time=(
                        selected.end_time
                    ),
                    duration=(
                        selected.duration
                    ),
                    preview_path=(
                        selected.preview_path
                    ),
                    semantic_score=round(
                        selected_score,
                        4,
                    ),
                )
            )

        return output

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

    def _clip_embedding(
        self,
        clip: IndexedSourceClip,
    ) -> torch.Tensor | None:

        cache_key = str(
            clip.preview_path
        )

        cached = (
            self._embedding_cache.get(
                cache_key
            )
        )

        if cached is not None:
            return cached

        path = Path(
            clip.preview_path
        )

        if not path.exists():
            return None

        try:

            image = (
                Image.open(
                    path
                )
                .convert(
                    "RGB"
                )
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

            self._embedding_cache[
                cache_key
            ] = features

            return features

        except Exception:
            return None

    def _text_embedding(
        self,
        query: str,
    ) -> torch.Tensor:

        tokens = (
            self.tokenizer(
                [
                    query,
                    (
                        "cinematic visual of "
                        + query
                    ),
                    (
                        "close relevant footage of "
                        + query
                    ),
                ]
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
            # Average the prompt variants.
            ################################################

            features = (
                features.mean(
                    dim=0,
                    keepdim=True,
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
