"""Resolve trusted YouTube release evidence from persisted production state."""

from __future__ import annotations

import json
from typing import Any

from backend.models.production_cycle import (
    ProductionCycleStatus,
)
from backend.services.production_cycle_service import (
    ProductionCycleService,
)


class YoutubeReleaseEvidenceService:
    """
    Resolve release evidence from Jarvis-owned persisted production state.

    Caller-provided production-result dictionaries are deliberately not
    accepted. The caller supplies only a cycle_id; production evidence is
    reconstructed from the persisted ProductionCycleRecord.
    """

    def __init__(
        self,
        *,
        cycle_service: ProductionCycleService | None = None,
    ) -> None:
        self.cycle_service = (
            cycle_service
            or ProductionCycleService()
        )

    async def resolve(
        self,
        session,
        *,
        cycle_id: str,
    ) -> dict[str, Any]:
        clean_cycle_id = str(
            cycle_id or ""
        ).strip()

        if not clean_cycle_id:
            raise ValueError(
                "cycle_id cannot be empty."
            )

        record = await self.cycle_service.get_cycle(
            session,
            clean_cycle_id,
        )

        if record is None:
            raise ValueError(
                "Production cycle not found: "
                f"{clean_cycle_id}"
            )

        if str(record.id).strip() != clean_cycle_id:
            raise ValueError(
                "Persisted production cycle identity "
                "does not match the requested cycle."
            )

        if (
            record.status
            != ProductionCycleStatus.COMPLETED
        ):
            raise ValueError(
                "Production cycle is not completed."
            )

        raw_result = record.result

        if not isinstance(raw_result, str):
            raise ValueError(
                "Completed production cycle has no "
                "persisted result."
            )

        try:
            persisted = json.loads(
                raw_result
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Persisted production-cycle result "
                "is not valid JSON."
            ) from exc

        if not isinstance(persisted, dict):
            raise ValueError(
                "Persisted production-cycle result "
                "must be a JSON object."
            )

        persisted_cycle_id = str(
            persisted.get(
                "cycle_id",
                "",
            )
        ).strip()

        if (
            persisted_cycle_id
            and persisted_cycle_id
            != clean_cycle_id
        ):
            raise ValueError(
                "Persisted result cycle identity "
                "does not match its database record."
            )

        selected_trend = persisted.get(
            "selected_trend"
        )

        if not isinstance(
            selected_trend,
            dict,
        ):
            selected_trend = {}

        upload = persisted.get(
            "upload"
        )

        if not isinstance(
            upload,
            dict,
        ):
            upload = {}

        selection = selected_trend.get(
            "production_selection"
        )

        if not isinstance(
            selection,
            dict,
        ):
            selection = {}

        persisted_score = self._number(
            selection.get(
                "production_score"
            )
        )

        record_score = self._number(
            record.production_score
        )

        if (
            record_score is not None
            and persisted_score is not None
            and abs(
                record_score
                - persisted_score
            ) > 0.000001
        ):
            raise ValueError(
                "Persisted production score does not "
                "match the authoritative cycle record."
            )

        trusted_score = (
            record_score
            if record_score is not None
            else persisted_score
        )

        normalized_selection = dict(
            selection
        )

        normalized_selection[
            "production_score"
        ] = trusted_score

        normalized_trend = dict(
            selected_trend
        )

        normalized_trend[
            "production_selection"
        ] = normalized_selection

        return {
            "cycle_id": clean_cycle_id,
            "status": "completed",
            "selected_trend": normalized_trend,
            "upload": dict(upload),
        }

    @staticmethod
    def _number(
        value: Any,
    ) -> float | None:
        if isinstance(value, bool):
            return None

        if isinstance(
            value,
            (int, float),
        ):
            return float(value)

        return None
