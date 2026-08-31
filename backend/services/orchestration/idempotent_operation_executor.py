"""Idempotent execution boundary for production side effects."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from backend.models.production_operation import (
    ProductionOperationStatus,
)
from backend.services.orchestration.idempotency import (
    OperationType,
    build_idempotency_key,
)
from backend.services.orchestration.production_operation_service import (
    ProductionOperationService,
)


class IdempotentOperationExecutor:
    """Execute side effects through persistent idempotency claims."""

    def __init__(
        self,
        session_factory: Any,
        *,
        operation_service: ProductionOperationService | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.operation_service = (
            operation_service
            if operation_service is not None
            else ProductionOperationService()
        )

    @staticmethod
    def _decode_result(
        value: str | None,
    ) -> dict | None:
        """Decode a stored JSON result."""

        if value is None:
            return None

        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return None

        if isinstance(decoded, dict):
            return decoded

        return None

    async def execute(
        self,
        *,
        operation_type: OperationType,
        resource_id: str,
        operation: Callable[
            [],
            Awaitable[dict],
        ],
    ) -> dict:
        """Execute an operation at most once per persistent key."""

        key = build_idempotency_key(
            operation_type,
            resource_id,
        )

        async with self.session_factory() as session:
            record, claimed = (
                await self.operation_service.claim(
                    session,
                    idempotency_key=key,
                    operation_type=(
                        operation_type.value
                    ),
                    resource_id=resource_id.strip(),
                )
            )

            if not claimed:
                if (
                    record.status
                    == ProductionOperationStatus
                    .COMPLETED
                    .value
                ):
                    return {
                        "status": "completed",
                        "executed": False,
                        "idempotency_key": key,
                        "result": self._decode_result(
                            record.result
                        ),
                    }

                if (
                    record.status
                    == ProductionOperationStatus
                    .IN_PROGRESS
                    .value
                ):
                    return {
                        "status": "in_progress",
                        "executed": False,
                        "idempotency_key": key,
                    }

                if (
                    record.status
                    == ProductionOperationStatus
                    .RECONCILIATION_REQUIRED
                    .value
                ):
                    return {
                        "status": "reconciliation_required",
                        "executed": False,
                        "idempotency_key": key,
                        "error": record.error,
                    }

                if (
                    record.status
                    == ProductionOperationStatus
                    .FAILED
                    .value
                ):
                    if record.retry_authorized:
                        record, reclaimed = (
                            await self.operation_service
                            .reclaim_failed(
                                session,
                                idempotency_key=key,
                            )
                        )

                        if not reclaimed:
                            if (
                                record is not None
                                and record.status
                                == ProductionOperationStatus
                                .COMPLETED
                                .value
                            ):
                                return {
                                    "status": "completed",
                                    "executed": False,
                                    "idempotency_key": key,
                                    "result": (
                                        self._decode_result(
                                            record.result
                                        )
                                    ),
                                }

                            if (
                                record is not None
                                and record.status
                                == ProductionOperationStatus
                                .IN_PROGRESS
                                .value
                            ):
                                return {
                                    "status": "in_progress",
                                    "executed": False,
                                    "idempotency_key": key,
                                }

                            return {
                                "status": "blocked",
                                "executed": False,
                                "idempotency_key": key,
                            }

                        claimed = True

                    else:
                        return {
                            "status": "failed",
                            "executed": False,
                            "idempotency_key": key,
                            "error": record.error,
                        }

                if not claimed:
                    return {
                        "status": "blocked",
                        "executed": False,
                        "idempotency_key": key,
                    }

        try:
            result = await operation()

        except asyncio.CancelledError:
            async with self.session_factory() as session:
                current = (
                    await self.operation_service.get_by_key(
                        session,
                        key,
                    )
                )

                if (
                    current is not None
                    and current.status
                    == ProductionOperationStatus
                    .IN_PROGRESS
                    .value
                ):
                    await self.operation_service.fail(
                        session,
                        current,
                        error="operation_cancelled",
                    )

            raise

        except Exception as exc:
            async with self.session_factory() as session:
                current = (
                    await self.operation_service.get_by_key(
                        session,
                        key,
                    )
                )

                if (
                    current is not None
                    and current.status
                    == ProductionOperationStatus
                    .IN_PROGRESS
                    .value
                ):
                    await self.operation_service.fail(
                        session,
                        current,
                        error=str(exc),
                    )

            raise

        async with self.session_factory() as session:
            current = (
                await self.operation_service.get_by_key(
                    session,
                    key,
                )
            )

            if current is None:
                raise RuntimeError(
                    "Idempotent operation record disappeared."
                )

            await self.operation_service.complete(
                session,
                current,
                result=result,
            )

        return {
            "status": "completed",
            "executed": True,
            "idempotency_key": key,
            "result": result,
        }
