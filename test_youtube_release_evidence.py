"""Regression tests for persisted YouTube release evidence."""

import asyncio
import json
import tempfile
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from backend.models.production_cycle import (
    ProductionCycleRecord,
    ProductionCycleStatus,
)
from backend.services.orchestration.youtube_release_evidence import (
    YoutubeReleaseEvidenceService,
)


def build_result(
    *,
    cycle_id="cycle-release-001",
    score=88.0,
    privacy_status="private",
    video_id="youtube-video-123",
):
    return {
        "cycle_id": cycle_id,
        # Real ProductionOrchestrator result uses "success".
        "status": "success",
        "selected_trend": {
            "title": "Trusted release topic",
            "production_selection": {
                "eligible": True,
                "selected": True,
                "production_score": score,
            },
        },
        "upload": {
            "status": "completed",
            "privacy_status": privacy_status,
            "upload": {
                "status": "completed",
                "executed": True,
                "result": {
                    "video_id": video_id,
                },
            },
        },
    }


async def main():
    with tempfile.TemporaryDirectory() as temp_dir:
        database_path = (
            Path(temp_dir)
            / "youtube_release_evidence.db"
        )

        engine = create_async_engine(
            "sqlite+aiosqlite:///"
            + str(database_path)
        )

        session_factory = async_sessionmaker(
            engine,
            expire_on_commit=False,
        )

        async with engine.begin() as connection:
            await connection.run_sync(
                ProductionCycleRecord.__table__.create
            )

        service = YoutubeReleaseEvidenceService()

        # ----------------------------------------------------
        # Valid completed persisted cycle
        # ----------------------------------------------------

        result = build_result()

        async with session_factory() as session:
            session.add(
                ProductionCycleRecord(
                    id="cycle-release-001",
                    status=(
                        ProductionCycleStatus.COMPLETED
                    ),
                    selected_topic=(
                        "Trusted release topic"
                    ),
                    production_score=88.0,
                    result=json.dumps(result),
                )
            )

            await session.commit()

        async with session_factory() as session:
            evidence = await service.resolve(
                session,
                cycle_id="cycle-release-001",
            )

        assert evidence["cycle_id"] == (
            "cycle-release-001"
        )

        # DB terminal status becomes the policy-facing status.
        assert evidence["status"] == "completed"

        # Raw orchestrator result was "success", so this proves
        # caller/result status is not being blindly trusted.
        assert result["status"] == "success"

        assert (
            evidence[
                "selected_trend"
            ][
                "production_selection"
            ][
                "production_score"
            ]
            == 88.0
        )

        assert (
            evidence["upload"][
                "privacy_status"
            ]
            == "private"
        )

        assert (
            evidence["upload"][
                "upload"
            ][
                "result"
            ][
                "video_id"
            ]
            == "youtube-video-123"
        )

        print(
            "PASS: completed DB record resolves "
            "normalized trusted release evidence."
        )

        # ----------------------------------------------------
        # Unknown cycle
        # ----------------------------------------------------

        async with session_factory() as session:
            try:
                await service.resolve(
                    session,
                    cycle_id="missing-cycle",
                )
            except ValueError as exc:
                assert (
                    "not found"
                    in str(exc).lower()
                )
            else:
                raise AssertionError(
                    "Missing cycle must fail closed."
                )

        print(
            "PASS: unknown cycle fails closed."
        )

        # ----------------------------------------------------
        # Non-completed database state
        # ----------------------------------------------------

        async with session_factory() as session:
            session.add(
                ProductionCycleRecord(
                    id="cycle-started-001",
                    status=(
                        ProductionCycleStatus.STARTED
                    ),
                    result=json.dumps(
                        build_result(
                            cycle_id=(
                                "cycle-started-001"
                            )
                        )
                    ),
                )
            )

            await session.commit()

        async with session_factory() as session:
            try:
                await service.resolve(
                    session,
                    cycle_id="cycle-started-001",
                )
            except ValueError as exc:
                assert (
                    "not completed"
                    in str(exc).lower()
                )
            else:
                raise AssertionError(
                    "STARTED cycle must fail closed."
                )

        print(
            "PASS: database terminal state is authoritative."
        )

        # ----------------------------------------------------
        # Malformed persisted JSON
        # ----------------------------------------------------

        async with session_factory() as session:
            session.add(
                ProductionCycleRecord(
                    id="cycle-json-001",
                    status=(
                        ProductionCycleStatus.COMPLETED
                    ),
                    selected_topic="Bad JSON",
                    production_score=80.0,
                    result="{not-json",
                )
            )

            await session.commit()

        async with session_factory() as session:
            try:
                await service.resolve(
                    session,
                    cycle_id="cycle-json-001",
                )
            except ValueError as exc:
                assert (
                    "valid json"
                    in str(exc).lower()
                )
            else:
                raise AssertionError(
                    "Malformed persisted JSON "
                    "must fail closed."
                )

        print(
            "PASS: malformed persisted result fails closed."
        )

        # ----------------------------------------------------
        # Persisted cycle-id mismatch
        # ----------------------------------------------------

        mismatched = build_result(
            cycle_id="different-cycle",
        )

        async with session_factory() as session:
            session.add(
                ProductionCycleRecord(
                    id="cycle-identity-001",
                    status=(
                        ProductionCycleStatus.COMPLETED
                    ),
                    selected_topic="Identity test",
                    production_score=88.0,
                    result=json.dumps(
                        mismatched
                    ),
                )
            )

            await session.commit()

        async with session_factory() as session:
            try:
                await service.resolve(
                    session,
                    cycle_id="cycle-identity-001",
                )
            except ValueError as exc:
                assert (
                    "identity"
                    in str(exc).lower()
                )
            else:
                raise AssertionError(
                    "Cycle identity mismatch "
                    "must fail closed."
                )

        print(
            "PASS: persisted cycle identity mismatch "
            "fails closed."
        )

        # ----------------------------------------------------
        # Production-score tampering
        # ----------------------------------------------------

        tampered = build_result(
            cycle_id="cycle-score-001",
            score=99.0,
        )

        async with session_factory() as session:
            session.add(
                ProductionCycleRecord(
                    id="cycle-score-001",
                    status=(
                        ProductionCycleStatus.COMPLETED
                    ),
                    selected_topic="Score test",
                    production_score=75.0,
                    result=json.dumps(
                        tampered
                    ),
                )
            )

            await session.commit()

        async with session_factory() as session:
            try:
                await service.resolve(
                    session,
                    cycle_id="cycle-score-001",
                )
            except ValueError as exc:
                assert (
                    "production score"
                    in str(exc).lower()
                )
            else:
                raise AssertionError(
                    "Production-score mismatch "
                    "must fail closed."
                )

        print(
            "PASS: persisted score mismatch fails closed."
        )

        # ----------------------------------------------------
        # Empty cycle ID
        # ----------------------------------------------------

        async with session_factory() as session:
            try:
                await service.resolve(
                    session,
                    cycle_id="   ",
                )
            except ValueError as exc:
                assert (
                    "cannot be empty"
                    in str(exc).lower()
                )
            else:
                raise AssertionError(
                    "Empty cycle ID must fail closed."
                )

        print(
            "PASS: empty cycle identity fails closed."
        )

        await engine.dispose()

        print()
        print(
            "PASS: trusted YouTube release evidence "
            "regression suite complete."
        )


if __name__ == "__main__":
    asyncio.run(main())
