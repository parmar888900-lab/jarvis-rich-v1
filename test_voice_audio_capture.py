"""Regression tests for synchronized microphone capture."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
import wave

import numpy as np

from backend.services.voice.audio_capture import (
    AudioCapture,
)


def main():
    capture = AudioCapture(
        device=2,
    )

    assert capture.device == 2
    assert capture.sample_rate is None
    assert capture.channels == 1
    assert capture.dtype == "int16"
    assert capture.warmup_seconds == 0.5

    print(
        "PASS: native-rate capture is the default."
    )


    with patch(
        "backend.services.voice.audio_capture.sd.query_devices",
        return_value={
            "name": "Fake Microphone",
            "max_input_channels": 2,
            "default_samplerate": 44100.0,
        },
    ), patch(
        "backend.services.voice.audio_capture.sd.check_input_settings"
    ) as check:

        info = capture.get_device_info()

        assert info["name"] == "Fake Microphone"
        assert info["native_sample_rate"] == 44100
        assert info["capture_sample_rate"] == 44100

        check.assert_called_once_with(
            device=2,
            channels=1,
            samplerate=44100,
            dtype="int16",
        )

    print(
        "PASS: microphone native rate is discovered "
        "and validated."
    )


    override = AudioCapture(
        device=2,
        sample_rate=16000,
    )

    with patch(
        "backend.services.voice.audio_capture.sd.query_devices",
        return_value={
            "name": "Fake Microphone",
            "max_input_channels": 2,
            "default_samplerate": 44100.0,
        },
    ), patch(
        "backend.services.voice.audio_capture.sd.check_input_settings"
    ) as check:

        info = override.get_device_info()

        assert info["native_sample_rate"] == 44100
        assert info["capture_sample_rate"] == 16000

        check.assert_called_once_with(
            device=2,
            channels=1,
            samplerate=16000,
            dtype="int16",
        )

    print(
        "PASS: explicit sample-rate override remains supported."
    )


    with TemporaryDirectory() as directory:
        output = (
            Path(directory)
            / "capture.wav"
        )

        fake_stream = MagicMock()

        warmup = np.zeros(
            (22050, 1),
            dtype=np.int16,
        )

        recording = np.full(
            (4410, 1),
            100,
            dtype=np.int16,
        )

        fake_stream.read.side_effect = [
            (warmup, False),
            (recording, False),
        ]

        fake_context = MagicMock()
        fake_context.__enter__.return_value = (
            fake_stream
        )
        fake_context.__exit__.return_value = False

        ready_calls = []

        with patch.object(
            AudioCapture,
            "get_device_info",
            return_value={
                "name": "Fake Microphone",
                "max_input_channels": 2,
                "native_sample_rate": 44100,
                "capture_sample_rate": 44100,
            },
        ), patch(
            "backend.services.voice.audio_capture.sd.InputStream",
            return_value=fake_context,
        ) as input_stream:

            result = capture.record(
                output,
                duration_seconds=0.1,
                on_ready=lambda: ready_calls.append(
                    "ready"
                ),
            )

        input_stream.assert_called_once_with(
            device=2,
            samplerate=44100,
            channels=1,
            dtype="int16",
        )

        assert (
            fake_stream.read.call_args_list[0].args[0]
            == 22050
        )

        assert (
            fake_stream.read.call_args_list[1].args[0]
            == 4410
        )

        assert ready_calls == [
            "ready"
        ]

        assert result["status"] == "success"
        assert result["sample_rate"] == 44100
        assert result["native_sample_rate"] == 44100
        assert result["frames"] == 4410
        assert result["overflowed"] is False
        assert output.exists()

        with wave.open(
            str(output),
            "rb",
        ) as wav:
            assert wav.getnchannels() == 1
            assert wav.getframerate() == 44100
            assert wav.getsampwidth() == 2
            assert wav.getnframes() == 4410

    print(
        "PASS: microphone is warmed up before "
        "the ready callback and recording."
    )


    no_warmup = AudioCapture(
        device=2,
        warmup_seconds=0,
    )

    with TemporaryDirectory() as directory:
        output = (
            Path(directory)
            / "capture.wav"
        )

        fake_stream = MagicMock()

        recording = np.zeros(
            (4410, 1),
            dtype=np.int16,
        )

        fake_stream.read.return_value = (
            recording,
            False,
        )

        fake_context = MagicMock()
        fake_context.__enter__.return_value = (
            fake_stream
        )
        fake_context.__exit__.return_value = False

        with patch.object(
            AudioCapture,
            "get_device_info",
            return_value={
                "name": "Fake Microphone",
                "max_input_channels": 2,
                "native_sample_rate": 44100,
                "capture_sample_rate": 44100,
            },
        ), patch(
            "backend.services.voice.audio_capture.sd.InputStream",
            return_value=fake_context,
        ):

            no_warmup.record(
                output,
                duration_seconds=0.1,
            )

        assert fake_stream.read.call_count == 1
        assert (
            fake_stream.read.call_args.args[0]
            == 4410
        )

    print(
        "PASS: zero warm-up is supported explicitly."
    )


    for invalid in (
        0,
        -1,
        "invalid",
    ):
        try:
            capture.record(
                "unused.wav",
                duration_seconds=invalid,
            )
        except ValueError:
            pass
        else:
            raise AssertionError(
                "Invalid duration must fail."
            )

    print(
        "PASS: invalid durations fail closed."
    )


    try:
        capture.record(
            "unused.mp3",
            duration_seconds=1,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Non-WAV output must fail."
        )

    print(
        "PASS: non-WAV output is rejected."
    )


    invalid_constructors = [
        {
            "sample_rate": 0,
        },
        {
            "channels": 2,
        },
        {
            "dtype": "float32",
        },
        {
            "warmup_seconds": -1,
        },
    ]

    for kwargs in invalid_constructors:
        try:
            AudioCapture(
                **kwargs
            )
        except ValueError:
            pass
        else:
            raise AssertionError(
                f"Invalid configuration accepted: {kwargs}"
            )

    print(
        "PASS: invalid capture configuration fails closed."
    )


    print()
    print(
        "PASS: synchronized AudioCapture regression "
        "suite complete."
    )


if __name__ == "__main__":
    main()
