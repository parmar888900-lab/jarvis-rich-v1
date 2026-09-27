#!/usr/bin/env python3
"""Bound an entire benchmark or a single resumable stage, retaining all output.

Example (use the executable belonging to the existing render environment):
  python scripts/run_bounded.py --stage r14-render --timeout 1200 \
      --heartbeat 15 --log generated/benchmarks/r14/render.log -- \
      .venv/bin/python run_r14_benchmark.py

Exit codes: child exit code, 124 deadline, 130 interruption, 125 wrapper failure.
No shell is used; command arguments and environment variables are never logged.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import signal
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services.runtime.execution_watchdog import (  # noqa: E402
    ExecutionTimeoutError,
    ExecutionWatchdogError,
    run_bounded,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--timeout", type=float, required=True, help="Hard wall-clock seconds")
    parser.add_argument("--heartbeat", type=float, default=15.0)
    parser.add_argument("--grace", type=float, default=3.0, help="Bounded graceful termination seconds")
    parser.add_argument("--log", type=Path, help="Append child stdout/stderr here")
    parser.add_argument("--cwd", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")

    def interrupted(_signum, _frame):
        raise KeyboardInterrupt

    previous = {}
    for signum in (signal.SIGINT, signal.SIGTERM):
        previous[signum] = signal.signal(signum, interrupted)
    try:
        outcome = run_bounded(
            command, stage=args.stage, timeout_seconds=args.timeout,
            heartbeat_seconds=args.heartbeat, terminate_grace_seconds=args.grace,
            log_path=args.log, cwd=args.cwd,
        )
        # POSIX signal exits use the conventional 128+signal representation.
        return outcome.returncode if outcome.returncode >= 0 else 128 - outcome.returncode
    except ExecutionTimeoutError:
        return 124
    except KeyboardInterrupt:
        return 130
    except (ExecutionWatchdogError, ValueError, OSError) as exc:
        # Watchdog errors contain no command/env values; do not expose raw OS errors.
        message = str(exc) if isinstance(exc, (ExecutionWatchdogError, ValueError)) else type(exc).__name__
        print(f"execution_watchdog: {message}", file=sys.stderr, flush=True)
        return 125
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


if __name__ == "__main__":
    raise SystemExit(main())
