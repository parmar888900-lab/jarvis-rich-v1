import asyncio
from pathlib import Path

from moviepy import (
    ImageClip,
    VideoFileClip,
    concatenate_videoclips,
)

from backend.services.image_generation.flux_provider import (
    FluxProvider,
)
from backend.services.video.luxury_reference_timeline import (
    LuxuryReferenceTimeline,
)
from backend.services.video_renderer.moviepy_runtime import (
    configure_moviepy_ffmpeg,
)
from backend.services.runtime.runtime_config import (
    RuntimeConfig,
)


PROMPTS = [
    "premium luxury chronograph wristwatch, black ceramic bezel, white dial, extreme macro product photography, polished steel case, dramatic studio lighting, dark premium background, photorealistic, commercial watch cinematography, no text, no watermark",

    "high end mechanical chronograph watch dial macro, polished indices, subdials, sapphire crystal reflections, luxury advertising photography, cinematic studio lighting, ultra detailed, photorealistic, no text",

    "luxury chronograph pushers and winding crown extreme close up, brushed and polished stainless steel, premium watch advertisement, dramatic reflections, photorealistic, no text",

    "high end Swiss mechanical watch movement macro, gears bridges rotor and jewel bearings, premium horology photography, cinematic golden highlights, photorealistic, no text",

    "luxury wristwatch bracelet macro detail, polished steel links, premium black studio environment, shallow depth of field, commercial product cinematography, photorealistic, no text",

    "premium chronograph watch on wrist, elegant dark suit, cinematic luxury lifestyle shot, shallow depth of field, premium advertising photography, photorealistic, no text",

    "luxury racing chronograph wristwatch hero shot, black background, dramatic rim lighting, premium product advertisement, polished steel and ceramic details, photorealistic, no text",

    "mechanical watch balance wheel and escapement extreme macro, precision Swiss watchmaking, cinematic technical luxury photography, photorealistic, no text",

    "luxury chronograph side profile macro, pushers crown polished case, premium dark studio lighting, watch commercial photography, photorealistic, no text",

    "premium white dial chronograph close up, black ceramic bezel, detailed subdials, luxury watch advertising lighting, dramatic macro photography, photorealistic, no text",

    "high end watchmaker assembling mechanical chronograph movement with precision tools, luxury craftsmanship cinematic close up, photorealistic, no text",

    "luxury sports chronograph beside racing imagery, sophisticated premium editorial advertisement, dramatic cinematic lighting, photorealistic, no text",

    "premium chronograph clasp and bracelet detail, steel finishing macro photography, elegant dark environment, luxury advertising aesthetic, photorealistic, no text",

    "Swiss mechanical chronograph calibre isolated macro hero shot, intricate gears and bridges, premium studio advertisement, photorealistic, no text",

    "luxury chronograph wristwatch rotating hero product composition, dark premium studio background, bright controlled reflections, high-end commercial photography, photorealistic, no text",
]


async def generate_images():

    provider = FluxProvider()

    output = []

    print()
    print("========== GENERATING PREMIUM VISUALS ==========")

    for index, prompt in enumerate(
        PROMPTS,
        start=1,
    ):

        print(
            f"[{index}/{len(PROMPTS)}]",
            prompt[:70],
        )

        image = await provider.generate(
            prompt
        )

        output.append(
            Path(
                image.image_path
            )
        )

    return output


def find_real_rolex_source():

    candidates = sorted(
        Path(
            "generated/media/internet_archive"
        ).glob(
            "*782abe47b69c8243*.mp4"
        )
    )

    if not candidates:
        return None

    return candidates[0]


async def main():

    config = RuntimeConfig.from_environment()

    configure_moviepy_ffmpeg(
        config.ffmpeg_executable
    )

    images = await generate_images()

    if not images:
        raise RuntimeError(
            "FLUX produced no images."
        )

    real_source_path = (
        find_real_rolex_source()
    )

    print()
    print(
        "REAL ROLEX SOURCE:",
        real_source_path,
    )

    real_source = None

    if (
        real_source_path is not None
        and real_source_path.exists()
    ):
        real_source = VideoFileClip(
            str(
                real_source_path
            )
        )

    timeline = (
        LuxuryReferenceTimeline.shots()
    )

    clips = []

    try:

        for index, shot in enumerate(
            timeline
        ):

            duration = float(
                shot.duration
            )

            ################################################
            # Use real footage periodically, but don't let
            # the weak source dominate the benchmark.
            ################################################

            use_real = (
                real_source is not None
                and index in {
                    1,
                    6,
                    11,
                    16,
                    21,
                    26,
                }
            )

            if use_real:

                available = max(
                    0.0,
                    real_source.duration
                    - duration
                )

                ratio = (
                    index
                    / max(
                        len(timeline) - 1,
                        1,
                    )
                )

                start = (
                    available
                    * ratio
                )

                clip = (
                    real_source
                    .subclipped(
                        start,
                        start + duration,
                    )
                )

                scale = max(
                    LuxuryReferenceTimeline.WIDTH
                    / clip.w,
                    LuxuryReferenceTimeline.HEIGHT
                    / clip.h,
                )

                clip = clip.resized(
                    scale
                )

                clip = clip.cropped(
                    x_center=clip.w / 2,
                    y_center=clip.h / 2,
                    width=(
                        LuxuryReferenceTimeline.WIDTH
                    ),
                    height=(
                        LuxuryReferenceTimeline.HEIGHT
                    ),
                )

            else:

                image_path = images[
                    index
                    % len(images)
                ]

                clip = ImageClip(
                    str(
                        image_path
                    )
                )

                scale = max(
                    LuxuryReferenceTimeline.WIDTH
                    / clip.w,
                    LuxuryReferenceTimeline.HEIGHT
                    / clip.h,
                )

                ################################################
                # Alternate punch-in framing to avoid every
                # generated shot feeling identical.
                ################################################

                zoom_pattern = (
                    1.00,
                    1.04,
                    1.07,
                    1.025,
                    1.055,
                )

                scale *= zoom_pattern[
                    index
                    % len(
                        zoom_pattern
                    )
                ]

                clip = clip.resized(
                    scale
                )

                clip = clip.cropped(
                    x_center=clip.w / 2,
                    y_center=clip.h / 2,
                    width=(
                        LuxuryReferenceTimeline.WIDTH
                    ),
                    height=(
                        LuxuryReferenceTimeline.HEIGHT
                    ),
                )

                clip = clip.with_duration(
                    duration
                )

            clips.append(
                clip
            )

        print()
        print(
            "========== RENDERING BEST C$0 BENCHMARK =========="
        )

        final = concatenate_videoclips(
            clips,
            method="compose",
        )

        output_dir = (
            Path(
                config.generated_dir
            )
            / "videos"
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        output = (
            output_dir
            / (
                "Rolex_Daytona_"
                "BEST_C0_Benchmark.mp4"
            )
        )

        final.write_videofile(
            str(output),
            fps=60,
            codec="libx264",
            audio=False,
            logger=None,
        )

        print()
        print(
            "========== BENCHMARK COMPLETE =========="
        )

        print(
            "VIDEO:",
            output,
        )

        print(
            "SHOTS:",
            len(clips),
        )

        print(
            "DURATION:",
            round(
                final.duration,
                3,
            ),
        )

        print(
            "RESOLUTION:",
            "1080x2400",
        )

        print(
            "FPS:",
            60,
        )

        final.close()

    finally:

        for clip in clips:
            try:
                clip.close()
            except Exception:
                pass

        if real_source is not None:
            try:
                real_source.close()
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(main())
