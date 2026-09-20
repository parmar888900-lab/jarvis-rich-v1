"""Daily autonomous Rich V1 production batch."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.orchestration.production_scheduler import (
    ProductionScheduler,
)

logger = logging.getLogger(__name__)


class DailyProductionBatch:
    """
    Produce a fixed number of successful autonomous videos per day.

    State persists across application restarts.

    Failed production is bounded per supervisor pass and repeated
    failure enters a cooldown so external providers and local
    generation services are not hammered continuously.
    """

    def __init__(
        self,
        scheduler: ProductionScheduler,
        *,
        daily_target: int = 4,
        state_path: str | Path = (
            "generated/state/daily_batch_state.json"
        ),
        attempts_per_pass: int = 2,
        failure_cooldown_seconds: int = 60 * 60,
    ) -> None:

        if daily_target < 1:
            raise ValueError(
                "daily_target must be at least 1."
            )

        if attempts_per_pass < 1:
            raise ValueError(
                "attempts_per_pass must be at least 1."
            )

        if failure_cooldown_seconds < 0:
            raise ValueError(
                "failure_cooldown_seconds cannot be negative."
            )

        self.scheduler = scheduler
        self.daily_target = int(daily_target)
        self.state_path = Path(state_path)

        self.attempts_per_pass = int(
            attempts_per_pass
        )

        self.failure_cooldown_seconds = int(
            failure_cooldown_seconds
        )

        self.state_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._batch_lock = asyncio.Lock()

    async def run_daily_batch(
        self,
    ) -> dict[str, Any]:

        async with self._batch_lock:

            if not self.scheduler.enabled:
                return {
                    "status": "autonomy_disabled",
                    "successful": 0,
                    "daily_target": self.daily_target,
                }

            today = date.today().isoformat()
            state = self._load_state()

            if state.get("date") != today:

                state = {
                    "date": today,
                    "successful": 0,
                    "attempted": 0,
                    "results": [],
                    "cooldown_until": None,
                }

                self._save_state(state)

            successful = int(
                state.get("successful", 0)
            )

            if successful >= self.daily_target:

                return {
                    "status": "daily_quota_complete",
                    "date": today,
                    "successful": successful,
                    "daily_target": self.daily_target,
                }

            now = datetime.now(timezone.utc)

            cooldown_until_raw = state.get(
                "cooldown_until"
            )

            if cooldown_until_raw:

                try:
                    cooldown_until = (
                        datetime.fromisoformat(
                            str(cooldown_until_raw)
                        )
                    )

                    if cooldown_until.tzinfo is None:
                        cooldown_until = (
                            cooldown_until.replace(
                                tzinfo=timezone.utc
                            )
                        )

                    if now < cooldown_until:

                        return {
                            "status": "cooldown",
                            "date": today,
                            "successful": successful,
                            "daily_target": self.daily_target,
                            "cooldown_until": (
                                cooldown_until.isoformat()
                            ),
                        }

                except (TypeError, ValueError):
                    logger.warning(
                        "Invalid production cooldown state; "
                        "clearing it."
                    )

                state["cooldown_until"] = None

            results = list(
                state.get("results", [])
            )

            remaining = (
                self.daily_target - successful
            )

            max_batch_attempts = min(
                remaining,
                self.attempts_per_pass,
            )

            batch_attempts = 0
            pass_successes = 0

            while (
                successful < self.daily_target
                and batch_attempts < max_batch_attempts
            ):

                batch_attempts += 1

                logger.info(
                    "Starting autonomous production attempt %s/%s "
                    "for this supervisor pass. "
                    "Daily progress: %s/%s.",
                    batch_attempts,
                    max_batch_attempts,
                    successful,
                    self.daily_target,
                )

                result = await self.scheduler.run_once()

                status = str(
                    result.get(
                        "status",
                        "unknown",
                    )
                )

                record = {
                    "timestamp": datetime.now(
                        timezone.utc
                    ).isoformat(),
                    "status": status,
                    "result": result,
                }

                results.append(record)

                state["attempted"] = (
                    int(
                        state.get(
                            "attempted",
                            0,
                        )
                    )
                    + 1
                )

                if status == "success":

                    successful += 1
                    pass_successes += 1

                    state["successful"] = successful

                    # A success proves the pipeline is making
                    # forward progress. Clear previous cooldown.
                    state["cooldown_until"] = None

                state["results"] = results
                self._save_state(state)

                logger.info(
                    "Jarvis daily production progress: %s/%s.",
                    successful,
                    self.daily_target,
                )

            completed = (
                successful >= self.daily_target
            )

            # If this entire supervisor pass failed to produce
            # anything, wait before trying another batch.
            if (
                not completed
                and batch_attempts > 0
                and pass_successes == 0
                and self.failure_cooldown_seconds > 0
            ):

                cooldown_until = (
                    datetime.now(timezone.utc).timestamp()
                    + self.failure_cooldown_seconds
                )

                cooldown_dt = datetime.fromtimestamp(
                    cooldown_until,
                    tz=timezone.utc,
                )

                state["cooldown_until"] = (
                    cooldown_dt.isoformat()
                )

                self._save_state(state)

                logger.warning(
                    "Autonomous production made no progress "
                    "during this pass. Cooling down until %s.",
                    cooldown_dt.isoformat(),
                )

            return {
                "status": (
                    "daily_quota_complete"
                    if completed
                    else "daily_quota_incomplete"
                ),
                "date": today,
                "successful": successful,
                "daily_target": self.daily_target,
                "batch_attempts": batch_attempts,
                "pass_successes": pass_successes,
                "cooldown_until": state.get(
                    "cooldown_until"
                ),
            }

    def _load_state(
        self,
    ) -> dict[str, Any]:

        if not self.state_path.exists():
            return {}

        try:

            value = json.loads(
                self.state_path.read_text(
                    encoding="utf-8"
                )
            )

            if isinstance(value, dict):
                return value

        except Exception:

            logger.exception(
                "Could not read daily production state."
            )

        return {}

    def _save_state(
        self,
        state: dict[str, Any],
    ) -> None:

        temporary = (
            self.state_path.with_suffix(
                ".tmp"
            )
        )

        temporary.write_text(
            json.dumps(
                state,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )

        temporary.replace(
            self.state_path
        )
