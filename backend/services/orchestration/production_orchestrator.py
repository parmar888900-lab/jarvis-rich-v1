"""Production-cycle orchestration.

Coordinates analysis and production without placing workflow logic
inside Commander or individual agent handlers.
"""

from typing import Any

from backend.services.commander import Commander
from backend.services.orchestration.youtube_release_service import YoutubeReleaseService
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
        release_service: Any | None = None,
    ) -> None:
        self.commander = commander or Commander()
        self.cycle_service = cycle_service
        self.session_factory = session_factory
        self.release_service = (
            release_service
            or YoutubeReleaseService()
        )

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

            video = production.get(
                "video"
            )

            if not isinstance(
                video,
                dict,
            ):
                failure = classify_failure_category(
                    None,
                    detail=(
                        "Production succeeded but returned "
                        "no rendered video artifact."
                    ),
                )

                result = {
                    "cycle_id": cycle_id,
                    "status": "production_artifact_missing",
                    "failure": failure.to_dict(),
                    "analysis": analysis,
                    "production": production,
                }

                await self._fail_cycle(
                    cycle_id,
                    result,
                )

                return result

            video_path = video.get(
                "video_path"
            )

            if (
                not isinstance(video_path, str)
                or not video_path.strip()
            ):
                failure = classify_failure_category(
                    None,
                    detail=(
                        "Production returned an invalid "
                        "rendered video path."
                    ),
                )

                result = {
                    "cycle_id": cycle_id,
                    "status": "production_artifact_missing",
                    "failure": failure.to_dict(),
                    "analysis": analysis,
                    "production": production,
                }

                await self._fail_cycle(
                    cycle_id,
                    result,
                )

                return result

            generated_content = production.get(
                "generated_content",
                {},
            )

            if not isinstance(
                generated_content,
                dict,
            ):
                generated_content = {}

            title = str(
                generated_content.get(
                    "title"
                )
                or trend.get(
                    "title"
                )
                or "Jarvis Short"
            ).strip()

            raw_tags = generated_content.get(
                "hashtags",
                [],
            )

            tags = (
                raw_tags
                if isinstance(raw_tags, list)
                else []
            )

            upload = await self.commander.route(
                agent="youtube",
                task="upload_video",
                command_id=f"{cycle_id}:upload",
                parameters={
                    "video_path": video_path,
                    "title": title,
                    "tags": tags,
                    "privacy_status": "private",
                },
            )

            if (
                upload.get("status")
                != "completed"
            ):
                failure = classify_failure_category(
                    upload.get(
                        "failure_category"
                    ),
                    detail=(
                        upload.get("error")
                        or (
                            "YouTube upload did not "
                            "complete successfully."
                        )
                    ),
                )

                result = {
                    "cycle_id": cycle_id,
                    "status": "upload_failed",
                    "failure": failure.to_dict(),
                    "selected_trend": trend,
                    "analysis": analysis,
                    "production": production,
                    "upload": upload,
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
                "upload": upload,
            }

            production_score = selection.get(
                "production_score"
            )

            # Persist the completed private-upload cycle first.
            # YoutubeReleaseEvidenceService evaluates this stored
            # result before public release is authorized.
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

            # Public publishing requires separate, explicit account-owner
            # authorization. Successful production/private upload is not it.
            import os
            if os.environ.get("JARVIS_PUBLIC_PUBLISH_ENABLED", "").strip().lower() != "true":
                result["release"] = {
                    "status": "disabled",
                    "reason": "Public publishing is disabled; explicit authorization is required.",
                }
                return result

            # Autonomous production is the trusted approval
            # boundary. The existing release policy still
            # validates the completed cycle, score, upload
            # evidence, video identity, and target visibility.
            release = await self.release_service.release_cycle(
                cycle_id=cycle_id,
                manual_approved=True,
            )

            result["release"] = release

            if release.get("status") not in {
                "completed",
                "already_completed",
            }:
                result["status"] = "release_failed"
                result["failure"] = {
                    "category": "youtube_release",
                    "retryable": False,
                    "detail": (
                        "Private upload completed but public "
                        "release was not completed."
                    ),
                }
                return result

            # PUBLIC RELEASE SUCCESS BOUNDARY
            #
            # Only now may the six-format rotation advance.
            # Topic reservation already happens in the selector so a
            # failed attempt does not immediately reuse the same topic.
            youtube_handler = getattr(
                self.commander,
                "agents",
                {},
            ).get("youtube")

            if youtube_handler is None:
                youtube_handler = getattr(
                    self.commander,
                    "handlers",
                    {},
                ).get("youtube")

            if youtube_handler is not None:
                selector = getattr(
                    youtube_handler,
                    "selector",
                    None,
                )
                format_rotator = getattr(
                    youtube_handler,
                    "format_rotator",
                    None,
                )

                if (
                    selector is not None
                    and format_rotator is not None
                ):
                    selector._format_cursor = (
                        format_rotator.next_cursor(
                            cursor=selector._format_cursor,
                            produced_count=1,
                        )
                    )
                    selector._save_state()

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



