import asyncio

from backend.services.video.caption_aligner import CaptionAligner


async def main():

    aligner = CaptionAligner()

    phrases = await aligner.align_phrases(
        "generated/packages/"
        "Piper_Production_Test/"
        "Piper_Production_Test.wav"
    )

    print("PHRASE COUNT:", len(phrases))

    for phrase in phrases:
        print(
            f"{phrase['start_time']:.3f} -> "
            f"{phrase['end_time']:.3f} | "
            f"{phrase['text']}"
        )


asyncio.run(main())
