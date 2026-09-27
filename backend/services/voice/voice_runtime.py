"""Always-on runtime for the Jarvis voice assistant."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from backend.services.network.instance_lock import instance_lock
from backend.services.network.heartbeat import write_heartbeat


logger = logging.getLogger(__name__)

VOICE_DIR = Path("generated") / "voice_runtime"
COMMAND_AUDIO = VOICE_DIR / "command.wav"
CONFIRMATION_AUDIO = VOICE_DIR / "confirmation.wav"
HEARTBEAT = Path("generated/state/voice.json")
VoiceAssistant = None
AudioCapture = None


async def run_voice_runtime() -> None:
    """Continuously listen for Jarvis voice interactions."""

    VOICE_DIR.mkdir(parents=True, exist_ok=True)

    assistant_type, capture_type = VoiceAssistant, AudioCapture
    if assistant_type is None:
        from backend.services.voice.assistant import VoiceAssistant as assistant_type
    if capture_type is None:
        from backend.services.voice.audio_capture import AudioCapture as capture_type
    assistant = assistant_type(
        audio_capture=capture_type(),
    )

    print("Jarvis voice runtime started.")
    print('Listening for "Jarvis"...')

    failures = 0
    while True:
        try:
            write_heartbeat(HEARTBEAT, state="WAKE_LISTENING")
            response = await assistant.interact_once(
                COMMAND_AUDIO,
                confirmation_audio_path=CONFIRMATION_AUDIO,
                duration_seconds=5.0,
                confirmation_duration_seconds=4.0,
                on_ready=lambda: print(
                    'Listening for "Jarvis"...'
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
            failures = 0
            write_heartbeat(HEARTBEAT, state="WAKE_LISTENING",
                            detail=result.status)

        except KeyboardInterrupt:
            raise

        except asyncio.CancelledError:
            raise

        except Exception:
            write_heartbeat(HEARTBEAT, state="ERROR", detail="voice_interaction_failed")
            logger.exception(
                "Voice interaction failed; continuing."
            )
            failures += 1
            await asyncio.sleep(min(60, 2 ** min(failures, 6)))


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s %(levelname)s "
            "%(name)s: %(message)s"
        ),
    )

    try:
        with instance_lock(Path("generated/state/voice_runtime.lock")):
            asyncio.run(run_voice_runtime())
    except KeyboardInterrupt:
        print("\nJarvis voice runtime stopped.")


if __name__ == "__main__":
    main()
