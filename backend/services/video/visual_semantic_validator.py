"""Visual-semantic validation for Rich V1 media candidates."""

from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
from pathlib import Path

import torch
from PIL import Image

import open_clip

from backend.services.storyboard.movie_visual_beat_planner import (
    MovieVisualBeat,
)
from backend.services.video.media_asset import MediaAsset


class VisualSemanticValidator:
    """
    Compare actual media content against the visual intent of a beat.

    Uses CLIP-style image/text embeddings. Video candidates are
    represented by a frame extracted with FFmpeg.
    """

    MODEL_NAME = "ViT-B-32"
    PRETRAINED = "laion2b_s34b_b79k"

    # Conservative V1 thresholds.
    MIN_SCORE = 0.185
    STRONG_SCORE = 0.26

    def __init__(
        self,
        *,
        ffmpeg_binary: str | None = None,
        device: str | None = None,
    ) -> None:

        self.ffmpeg_binary = (
            ffmpeg_binary
            or shutil.which("ffmpeg")
            or "ffmpeg"
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

    def validate(
        self,
        *,
        asset: MediaAsset,
        beat: MovieVisualBeat,
        movie_title: str,
    ) -> dict:

        frame_path = self._representative_image(
            asset
        )

        if frame_path is None:
            return {
                "valid": False,
                "score": 0.0,
                "reason": "representative_frame_unavailable",
            }

        try:

            score = self._similarity(
                image_path=frame_path,
                beat=beat,
                movie_title=movie_title,
            )

        finally:

            if (
                asset.asset_type == "video"
                and frame_path.exists()
            ):
                try:
                    frame_path.unlink()
                except OSError:
                    pass

        valid = (
            score >= self.MIN_SCORE
        )

        return {
            "valid": valid,
            "score": round(
                score,
                4,
            ),
            "reason": (
                "semantic_match"
                if valid
                else "semantic_mismatch"
            ),
            "strength": (
                "strong"
                if score >= self.STRONG_SCORE
                else (
                    "acceptable"
                    if valid
                    else "weak"
                )
            ),
        }

    def _similarity(
        self,
        *,
        image_path: Path,
        beat: MovieVisualBeat,
        movie_title: str,
    ) -> float:

        self._ensure_model()

        image = Image.open(
            image_path
        ).convert(
            "RGB"
        )

        image_tensor = (
            self.preprocess(
                image
            )
            .unsqueeze(0)
            .to(self.device)
        )

        prompts = self._text_prompts(
            beat=beat,
            movie_title=movie_title,
        )

        text_tokens = (
            self.tokenizer(
                prompts
            )
            .to(self.device)
        )

        with torch.no_grad():

            image_features = (
                self.model.encode_image(
                    image_tensor
                )
            )

            text_features = (
                self.model.encode_text(
                    text_tokens
                )
            )

            image_features = (
                image_features
                / image_features.norm(
                    dim=-1,
                    keepdim=True,
                )
            )

            text_features = (
                text_features
                / text_features.norm(
                    dim=-1,
                    keepdim=True,
                )
            )

            similarities = (
                image_features
                @ text_features.T
            )

        best = float(
            similarities.max().item()
        )

        if math.isnan(best):
            return 0.0

        return best

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

    @staticmethod
    def _text_prompts(
        *,
        beat: MovieVisualBeat,
        movie_title: str,
    ) -> list[str]:

        query = " ".join(
            beat.visual_query.split()
        )

        purpose_map = {
            "hook_subject": (
                "cinematic subject establishing shot"
            ),
            "hook_detail": (
                "cinematic visual detail"
            ),
            "filmmaker_context": (
                "film director or filmmaking production context"
            ),
            "explanation": (
                "visual explanation matching the narration"
            ),
            "technical_detail": (
                "visual effects or filmmaking technical detail"
            ),
            "supporting_visual": (
                "supporting cinematic visual"
            ),
            "payoff": (
                "strong cinematic payoff visual"
            ),
            "closing_visual": (
                "strong cinematic closing visual"
            ),
        }

        purpose = purpose_map.get(
            beat.purpose,
            "cinematic visual"
        )

        return [
            query,
            f"{query}, {purpose}",
            (
                f"{movie_title} commentary visual: "
                f"{query}"
            ),
        ]

    def _representative_image(
        self,
        asset: MediaAsset,
    ) -> Path | None:

        source = Path(
            asset.file_path
        )

        if not source.exists():
            return None

        if asset.asset_type == "image":
            return source

        if asset.asset_type != "video":
            return None

        temp_dir = Path(
            tempfile.gettempdir()
        )

        output = (
            temp_dir
            / (
                "jarvis_visual_"
                f"{asset.asset_id}.jpg"
            )
        )

        command = [
            self.ffmpeg_binary,
            "-y",
            "-loglevel",
            "error",
            "-ss",
            "1.0",
            "-i",
            str(source),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(output),
        ]

        try:

            completed = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=45,
            )

        except (
            OSError,
            subprocess.TimeoutExpired,
        ):
            return None

        if (
            completed.returncode != 0
            or not output.exists()
        ):
            return None

        return output

