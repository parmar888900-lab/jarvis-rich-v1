"""Production-cycle orchestration.

Coordinates analysis and production without placing workflow logic
inside Commander or individual agent handlers.
"""

from typing import Any

from backend.services.commander import Commander
from backend.services.orchestration.failure_classification import (
    classify_failure_category,
)
from backend.services.production_cycle_service import (
    ProductionCycleService,
)


class ProductionOrchestrator:
    """Coordinate a single analysis-to-production cycle."""

    NO_ACTION_ANALYSIS_STATUSES = {
        "no_trends_found",
        "no_production_ready_topic",
    }

    def __init__(
        self,
        commander: Commander | None = None,
        cycle_service: ProductionCycleService | None = None,
        session_factory: Any | None = None,
    ) -> None:
        self.commander = commander or Commander()
        self.cycle_service = cycle_service
        self.session_factory = session_factory

    async def run_cycle(
        self,
        cycle_id: str,
    ) -> dict:
        """Analyze trends and produce one selected video."""

        await self._start_cycle(
            cycle_id
        )

        try:
            analysis = await self.commander.route(
                agent="youtube",
                task="analyze_trends",
                command_id=f"{cycle_id}:analyze",
            )

            analysis_status = analysis.get(
                "status"
            )

            if (
                analysis_status
                in self.NO_ACTION_ANALYSIS_STATUSES
            ):
                result = {
                    "cycle_id": cycle_id,
                    "status": "no_action",
                    "reason": analysis_status,
                    "analysis": analysis,
                }

                await self._mark_no_action(
                    cycle_id,
                    result,
                )

                return result

            if analysis_status != "success":
                failure = classify_failure_category(
                    analysis.get(
                        "failure_category"
                    ),
                    detail=analysis.get(
                        "error"
                    ),
                )

                result = {
                    "cycle_id": cycle_id,
                    "status": "analysis_failed",
                    "failure": failure.to_dict(),
                    "analysis": analysis,
                }

                await self._fail_cycle(
                    cycle_id,
                    result,
                )

                return result

            trend = analysis.get(
                "best_trend"
            )

            if not isinstance(
                trend,
                dict,
            ):
                result = {
                    "cycle_id": cycle_id,
                    "status": "no_selected_trend",
                    "analysis": analysis,
                }

                await self._mark_no_action(
                    cycle_id,
                    result,
                )

                return result

            selection = trend.get(
                "production_selection",
                {},
            )

            if (
                not isinstance(selection, dict)
                or selection.get("eligible") is not True
                or selection.get("selected") is not True
            ):
                result = {
                    "cycle_id": cycle_id,
                    "status": "trend_not_authorized",
                    "analysis": analysis,
                }

                await self._mark_no_action(
                    cycle_id,
                    result,
                )

                return result

            production = await self.commander.route(
                agent="youtube",
                task="create_video",
                command_id=f"{cycle_id}:produce",
                parameters={
                    "trend": trend,
                },
            )

            if (
                production.get("status")
                != "success"
            ):
                failure = classify_failure_category(
                    production.get(
                        "failure_category"
                    ),
                    detail=production.get(
                        "error"
                    ),
                )

                result = {
                    "cycle_id": cycle_id,
                    "status": "production_failed",
                    "failure": failure.to_dict(),
                    "analysis": analysis,
                    "production": production,
                }

                await self._fail_cycle(
                    cycle_id,
                    result,
                )

                return result

            result = {
                "cycle_id": cycle_id,
                "status": "success",
                "selected_trend": trend,
                "analysis": analysis,
                "production": production,
            }

            production_score = selection.get(
                "production_score"
            )

            await self._complete_cycle(
                cycle_id,
                selected_topic=str(
                    trend.get(
                        "title",
                        "",
                    )
                ),
                production_score=(
                    float(production_score)
                    if production_score is not None
                    else None
                ),
                result=result,
            )

            return result

        except Exception as exc:
            failure = {
                "cycle_id": cycle_id,
                "status": "orchestration_failed",
                "error": str(exc),
            }

            try:
                await self._fail_cycle(
                    cycle_id,
                    failure,
                )
            except Exception:
                pass

            raise

    def _persistence_enabled(
        self,
    ) -> bool:
        return (
            self.cycle_service is not None
            and self.session_factory is not None
        )

    async def _start_cycle(
        self,
        cycle_id: str,
    ) -> None:
        if not self._persistence_enabled():
            return

        async with self.session_factory() as session:
            await self.cycle_service.start_cycle(
                session,
                cycle_id=cycle_id,
            )

    async def _complete_cycle(
        self,
        cycle_id: str,
        *,
        selected_topic: str,
        production_score: float | None,
        result: dict,
    ) -> None:
        if not self._persistence_enabled():
            return

        async with self.session_factory() as session:
            await self.cycle_service.complete_cycle(
                session,
                cycle_id,
                selected_topic=selected_topic,
                production_score=production_score,
                result=result,
            )

    async def _mark_no_action(
        self,
        cycle_id: str,
        result: dict,
    ) -> None:
        if not self._persistence_enabled():
            return

        async with self.session_factory() as session:
            await self.cycle_service.mark_no_action(
                session,
                cycle_id,
                result=result,
            )

    async def _fail_cycle(
        self,
        cycle_id: str,
        result: dict,
    ) -> None:
        if not self._persistence_enabled():
            return

        async with self.session_factory() as session:
            await self.cycle_service.fail_cycle(
                session,
                cycle_id,
                result=result,
            )



