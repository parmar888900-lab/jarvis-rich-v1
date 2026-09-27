#!/usr/bin/env python3
"""One isolated Whisper transcription launched only through the watchdog."""

import argparse
import json
from pathlib import Path

import whisper


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--model", default="tiny.en")
    args = parser.parse_args()
    if not args.audio.is_file():
        parser.error("Audio file missing")
    result = whisper.load_model(args.model).transcribe(str(args.audio), fp16=False)
    args.output.write_text(json.dumps({"status": "success", "text": result.get("text", ""),
                                       "model": args.model, "language": result.get("language")}),
                           encoding="utf-8")
