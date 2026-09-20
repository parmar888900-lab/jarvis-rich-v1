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

    State persists across application restarts so restarting Jarvis
    does not reset the daily successful-video count.
    """

    def __init__(
        self,
        scheduler: ProductionScheduler,
        *,
        daily_target: int = 4,
        state_path: str | Path = (
            "generated/state/daily_batch_state.json"
        ),
    ) -> None:

        if daily_target < 1:
            raise ValueError(
                "daily_target must be at least 1."
            )

        self.scheduler = scheduler
        self.daily_target = int(daily_target)
        self.state_path = Path(state_path)

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
                }

                self._save_state(
                    state
                )

            successful = int(
                state.get(
                    "successful",
                    0,
                )
            )

            if successful >= self.daily_target:

                return {
                    "status": "daily_quota_complete",
                    "date": today,
                    "successful": successful,
                    "daily_target": self.daily_target,
                }

            results = list(
                state.get(
                    "results",
                    [],
                )
            )

            remaining = (
                self.daily_target
                - successful
            )

            # Allow failures, but never loop forever unattended.
            max_batch_attempts = max(
                remaining * 2,
                remaining,
            )

            batch_attempts = 0

            while (
                successful < self.daily_target
                and batch_attempts < max_batch_attempts
            ):

                batch_attempts += 1

                logger.info(
                    "Starting autonomous production attempt %s. "
                    "Daily progress: %s/%s.",
                    batch_attempts,
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

                results.append(
                    record
                )

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

                    state["successful"] = (
                        successful
                    )

                state["results"] = results

                self._save_state(
                    state
                )

                logger.info(
                    "Jarvis daily production progress: %s/%s.",
                    successful,
                    self.daily_target,
                )

            completed = (
                successful
                >= self.daily_target
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

            if isinstance(
                value,
                dict,
            ):
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
