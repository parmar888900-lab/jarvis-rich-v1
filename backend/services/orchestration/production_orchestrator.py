"""Production-cycle orchestration.

Coordinates analysis and production without placing workflow logic
inside Commander or individual agent handlers.
"""

from backend.services.commander import Commander


class ProductionOrchestrator:
    """Coordinate a single analysis-to-production cycle."""

    def __init__(
        self,
        commander: Commander | None = None,
    ) -> None:
        self.commander = commander or Commander()

    async def run_cycle(
        self,
        cycle_id: str,
    ) -> dict:
        """Analyze trends and produce one selected video."""

        analysis = await self.commander.route(
            agent="youtube",
            task="analyze_trends",
            command_id=f"{cycle_id}:analyze",
        )

        if analysis.get("status") != "success":
            return {
                "cycle_id": cycle_id,
                "status": "analysis_failed",
                "analysis": analysis,
            }

        trend = analysis.get("best_trend")

        if not isinstance(trend, dict):
            return {
                "cycle_id": cycle_id,
                "status": "no_selected_trend",
                "analysis": analysis,
            }

        selection = trend.get(
            "production_selection",
            {},
        )

        if (
            not isinstance(selection, dict)
            or selection.get("eligible") is not True
            or selection.get("selected") is not True
        ):
            return {
                "cycle_id": cycle_id,
                "status": "trend_not_authorized",
                "analysis": analysis,
            }

        production = await self.commander.route(
            agent="youtube",
            task="create_video",
            command_id=f"{cycle_id}:produce",
            parameters={
                "trend": trend,
            },
        )

        if production.get("status") != "success":
            return {
                "cycle_id": cycle_id,
                "status": "production_failed",
                "analysis": analysis,
                "production": production,
            }

        return {
            "cycle_id": cycle_id,
            "status": "success",
            "selected_trend": trend,
            "analysis": analysis,
            "production": production,
        }
