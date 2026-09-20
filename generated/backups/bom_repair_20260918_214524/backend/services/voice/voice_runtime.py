"""Always-on runtime for the Jarvis voice assistant."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from backend.services.voice.assistant import VoiceAssistant
from backend.services.voice.audio_capture import AudioCapture


logger = logging.getLogger(__name__)

VOICE_DIR = Path("generated") / "voice_runtime"
COMMAND_AUDIO = VOICE_DIR / "command.wav"
CONFIRMATION_AUDIO = VOICE_DIR / "confirmation.wav"


async def run_voice_runtime() -> None:
    """Continuously listen for Jarvis voice interactions."""

    VOICE_DIR.mkdir(parents=True, exist_ok=True)

    assistant = VoiceAssistant(
        audio_capture=AudioCapture(device=2),
    )

    print("Jarvis voice runtime started.")
    print('Listening for "Hey Jarvis"...')

    while True:
        try:
            response = await assistant.interact_once(
                COMMAND_AUDIO,
                confirmation_audio_path=CONFIRMATION_AUDIO,
                duration_seconds=5.0,
                confirmation_duration_seconds=4.0,
                on_ready=lambda: print(
                    'Listening for "Hey Jarvis"...'
                ),
                on_confirmation_ready=lambda: print(
                    "Listening for confirmation..."
                ),
            )

            result = response.assistant_result

            print(
                f"Voice status={result.status} "
                f"transcript={result.transcript!r}"
            )

        except KeyboardInterrupt:
            raise

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception(
                "Voice interaction failed; continuing."
            )
            await asyncio.sleep(1)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s %(levelname)s "
            "%(name)s: %(message)s"
        ),
    )

    try:
        asyncio.run(run_voice_runtime())
    except KeyboardInterrupt:
        print("\nJarvis voice runtime stopped.")


if __name__ == "__main__":
    main()

