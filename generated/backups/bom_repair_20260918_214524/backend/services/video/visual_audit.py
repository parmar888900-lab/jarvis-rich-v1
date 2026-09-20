"""Visual audit generation for Rich V1 resolved movie media."""

from __future__ import annotations

import html
import json
import shutil
import subprocess
from pathlib import Path

from backend.services.video.movie_media_resolver import (
    ResolvedMovieBeat,
)


class VisualAuditGenerator:
    """
    Build a human-reviewable audit of resolved visual assets.

    Images are converted to audit thumbnails.
    Videos use a representative frame extracted with FFmpeg.
    """

    THUMB_WIDTH = 540
    THUMB_HEIGHT = 960

    def __init__(
        self,
        *,
        ffmpeg_binary: str = "ffmpeg",
    ) -> None:

        self.ffmpeg_binary = ffmpeg_binary

    def generate(
        self,
        *,
        resolved_beats: list[ResolvedMovieBeat],
        content_id: str,
        output_root: str | Path = "generated/audits",
    ) -> Path:

        clean_content_id = str(
            content_id
        ).strip()

        if not clean_content_id:
            raise RuntimeError(
                "Visual audit requires content_id."
            )

        output_dir = (
            Path(output_root)
            / clean_content_id
        )

        thumbnails_dir = (
            output_dir
            / "thumbnails"
        )

        thumbnails_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        records: list[dict] = []

        for item in resolved_beats:

            record = self._build_record(
                item=item,
                thumbnails_dir=thumbnails_dir,
            )

            records.append(record)

        json_path = (
            output_dir
            / "audit.json"
        )

        json_path.write_text(
            json.dumps(
                records,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        html_path = (
            output_dir
            / "audit.html"
        )

        html_path.write_text(
            self._build_html(
                content_id=clean_content_id,
                records=records,
            ),
            encoding="utf-8",
        )

        return html_path

    def _build_record(
        self,
        *,
        item: ResolvedMovieBeat,
        thumbnails_dir: Path,
    ) -> dict:

        asset = item.asset

        if asset is None:

            return {
                "beat_id": item.beat_id,
                "status": "unresolved",
                "purpose": item.purpose,
                "visual_query": item.visual_query,
                "target_duration": item.target_duration,
                "evidence_ids": list(
                    item.evidence_ids
                ),
                "attempted_queries": list(
                    item.attempted_queries
                ),
                "thumbnail": None,
            }

        source_path = Path(
            asset.file_path
        )

        if not source_path.exists():

            return {
                "beat_id": item.beat_id,
                "status": "asset_missing",
                "purpose": item.purpose,
                "visual_query": item.visual_query,
                "file_path": str(
                    source_path
                ),
                "thumbnail": None,
            }

        thumb_path = (
            thumbnails_dir
            / f"{item.beat_id}.jpg"
        )

        thumbnail_ok = (
            self._create_thumbnail(
                source_path=source_path,
                asset_type=asset.asset_type,
                output_path=thumb_path,
            )
        )

        relative_thumb = None

        if thumbnail_ok:
            relative_thumb = (
                "thumbnails/"
                + thumb_path.name
            )

        return {
            "beat_id": item.beat_id,
            "status": item.status,
            "purpose": item.purpose,
            "visual_query": item.visual_query,
            "target_duration": (
                item.target_duration
            ),
            "evidence_ids": list(
                item.evidence_ids
            ),
            "attempted_queries": list(
                item.attempted_queries
            ),
            "asset_id": asset.asset_id,
            "asset_type": asset.asset_type,
            "file_path": asset.file_path,
            "source_url": asset.source_url,
            "source_name": asset.source_name,
            "creator": asset.creator,
            "license_name": asset.license_name,
            "license_url": asset.license_url,
            "commercial_use_allowed": (
                asset.commercial_use_allowed
            ),
            "relevance_score": (
                asset.relevance_score
            ),
            "duration": asset.duration,
            "width": asset.width,
            "height": asset.height,
            "content_id": asset.content_id,
            "thumbnail": relative_thumb,
        }

    def _create_thumbnail(
        self,
        *,
        source_path: Path,
        asset_type: str,
        output_path: Path,
    ) -> bool:

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if asset_type == "video":

            return self._video_thumbnail(
                source_path=source_path,
                output_path=output_path,
            )

        if asset_type == "image":

            return self._image_thumbnail(
                source_path=source_path,
                output_path=output_path,
            )

        return False

    def _video_thumbnail(
        self,
        *,
        source_path: Path,
        output_path: Path,
    ) -> bool:

        command = [
            self.ffmpeg_binary,
            "-y",
            "-loglevel",
            "error",
            "-ss",
            "1.0",
            "-i",
            str(source_path),
            "-frames:v",
            "1",
            "-vf",
            (
                "scale="
                f"{self.THUMB_WIDTH}:"
                f"{self.THUMB_HEIGHT}:"
                "force_original_aspect_ratio=decrease,"
                "pad="
                f"{self.THUMB_WIDTH}:"
                f"{self.THUMB_HEIGHT}:"
                "(ow-iw)/2:(oh-ih)/2"
            ),
            "-q:v",
            "3",
            str(output_path),
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
            return False

        return (
            completed.returncode == 0
            and output_path.exists()
        )

    def _image_thumbnail(
        self,
        *,
        source_path: Path,
        output_path: Path,
    ) -> bool:

        try:
            from PIL import (
                Image,
                ImageOps,
            )

            with Image.open(
                source_path
            ) as image:

                image = image.convert(
                    "RGB"
                )

                canvas = ImageOps.pad(
                    image,
                    (
                        self.THUMB_WIDTH,
                        self.THUMB_HEIGHT,
                    ),
                    method=(
                        Image.Resampling.LANCZOS
                    ),
                    color=(
                        20,
                        20,
                        20,
                    ),
                )

                canvas.save(
                    output_path,
                    format="JPEG",
                    quality=88,
                )

        except Exception:
            return False

        return output_path.exists()

    @staticmethod
    def _build_html(
        *,
        content_id: str,
        records: list[dict],
    ) -> str:

        cards: list[str] = []

        for record in records:

            thumbnail = record.get(
                "thumbnail"
            )

            if thumbnail:

                visual = (
                    '<img class="thumb" src="'
                    + html.escape(
                        thumbnail
                    )
                    + '" alt="'
                    + html.escape(
                        record.get(
                            "beat_id",
                            "",
                        )
                    )
                    + '">'
                )

            else:

                visual = (
                    '<div class="missing">'
                    'NO THUMBNAIL'
                    '</div>'
                )

            score = record.get(
                "relevance_score"
            )

            score_text = (
                str(score)
                if score is not None
                else "N/A"
            )

            attempted = record.get(
                "attempted_queries",
                [],
            )

            attempted_html = "".join(
                "<li>"
                + html.escape(
                    str(query)
                )
                + "</li>"
                for query in attempted
            )

            source_url = str(
                record.get(
                    "source_url",
                    "",
                )
                or ""
            )

            if source_url:

                source_display = (
                    '<a href="'
                    + html.escape(
                        source_url
                    )
                    + '" target="_blank">'
                    + "Open source"
                    + "</a>"
                )

            else:

                source_display = "N/A"

            card = f"""
            <article class="card">
                {visual}

                <div class="info">
                    <h2>{html.escape(str(record.get("beat_id", "")))}</h2>

                    <div class="score">
                        Score: {html.escape(score_text)}
                    </div>

                    <p>
                        <strong>Purpose:</strong>
                        {html.escape(str(record.get("purpose", "")))}
                    </p>

                    <p>
                        <strong>Query:</strong>
                        {html.escape(str(record.get("visual_query", "")))}
                    </p>

                    <p>
                        <strong>Asset:</strong>
                        {html.escape(str(record.get("asset_type", "")))}
                    </p>

                    <p>
                        <strong>Provider:</strong>
                        {html.escape(str(record.get("source_name", "")))}
                    </p>

                    <p>
                        <strong>License:</strong>
                        {html.escape(str(record.get("license_name", "")))}
                    </p>

                    <p>
                        <strong>Resolution:</strong>
                        {html.escape(str(record.get("width", "")))}
                        ×
                        {html.escape(str(record.get("height", "")))}
                    </p>

                    <p>
                        <strong>Duration:</strong>
                        {html.escape(str(record.get("duration", "")))}
                    </p>

                    <p>
                        <strong>Target:</strong>
                        {html.escape(str(record.get("target_duration", "")))}s
                    </p>

                    <p>
                        <strong>Evidence:</strong>
                        {html.escape(str(record.get("evidence_ids", [])))}
                    </p>

                    <p>
                        <strong>Source:</strong>
                        {source_display}
                    </p>

                    <details>
                        <summary>Attempted queries</summary>
                        <ol>
                            {attempted_html}
                        </ol>
                    </details>

                    <details>
                        <summary>Local file</summary>
                        <code>
                            {html.escape(str(record.get("file_path", "")))}
                        </code>
                    </details>
                </div>
            </article>
            """

            cards.append(card)

        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta
    name="viewport"
    content="width=device-width, initial-scale=1"
>
<title>Rich V1 Visual Audit</title>

<style>
    * {{
        box-sizing: border-box;
    }}

    body {{
        margin: 0;
        background: #101114;
        color: #f4f4f4;
        font-family:
            Inter,
            Arial,
            sans-serif;
    }}

    header {{
        padding: 28px;
        border-bottom:
            1px solid #303238;
    }}

    header h1 {{
        margin: 0 0 8px 0;
    }}

    header p {{
        margin: 0;
        color: #aeb2bb;
    }}

    main {{
        display: grid;
        grid-template-columns:
            repeat(
                auto-fit,
                minmax(330px, 1fr)
            );
        gap: 22px;
        padding: 24px;
    }}

    .card {{
        background: #191b20;
        border:
            1px solid #303238;
        border-radius: 14px;
        overflow: hidden;
    }}

    .thumb {{
        display: block;
        width: 100%;
        aspect-ratio: 9 / 16;
        object-fit: contain;
        background: #08090b;
    }}

    .missing {{
        width: 100%;
        aspect-ratio: 9 / 16;
        display: grid;
        place-items: center;
        background: #08090b;
        color: #888;
    }}

    .info {{
        padding: 18px;
    }}

    .info h2 {{
        margin:
            0 0 10px 0;
    }}

    .score {{
        display: inline-block;
        padding:
            6px 10px;
        margin-bottom: 10px;
        border-radius: 999px;
        background: #292c33;
        font-weight: 700;
    }}

    p {{
        line-height: 1.45;
    }}

    strong {{
        color: #cdd2dc;
    }}

    a {{
        color: #8ab4ff;
    }}

    details {{
        margin-top: 12px;
    }}

    code {{
        display: block;
        margin-top: 8px;
        white-space: normal;
        overflow-wrap: anywhere;
        color: #b8bec9;
    }}

    li {{
        margin-bottom: 5px;
    }}
</style>
</head>

<body>

<header>
    <h1>Jarvis Rich V1 — Visual Audit</h1>
    <p>
        Content ID:
        {html.escape(content_id)}
        · Beats:
        {len(records)}
    </p>
</header>

<main>
    {''.join(cards)}
</main>

</body>
</html>
"""


