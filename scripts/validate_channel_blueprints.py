#!/usr/bin/env python3
"""Validate unregistered channel proposals; optionally compare real 1–60 roster.

The JSON roster is a list of {"name": ..., "handle": ...} objects. This
never registers accounts, mutates SQLite, or enables production/publishing.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.services.network.channel_blueprints import proposed_channels, validate_blueprints


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--existing-roster", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    existing = json.loads(args.existing_roster.read_text(encoding="utf-8")) if args.existing_roster else []
    if not isinstance(existing, list):
        raise ValueError("Existing roster must be a JSON array")
    outcome = validate_blueprints(existing)
    if args.output:
        args.output.write_text(json.dumps(proposed_channels(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(outcome, sort_keys=True))


if __name__ == "__main__":
    main()
