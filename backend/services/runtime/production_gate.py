"""Production readiness gate for autonomous execution."""

from __future__ import annotations

from dataclasses import dataclass

from backend.services.runtime.capabilities import (
    RuntimeCapabilityReport,
)


@dataclass(frozen=True)
class ProductionReadinessDecision:
    """Whether autonomous production may execute."""

    autonomous_requested: bool
    production_ready: bool
    scheduler_enabled: bool
    missing_required: tuple[str, ...]

    @property
    def blocked(self) -> bool:
        return (
            self.autonomous_requested
            and not self.production_ready
        )

    def as_dict(self) -> dict:
        return {
            "autonomous_requested":
                self.autonomous_requested,
            "production_ready":
                self.production_ready,
            "scheduler_enabled":
                self.scheduler_enabled,
            "blocked":
                self.blocked,
            "missing_required":
                list(
                    self.missing_required
                ),
        }


def evaluate_production_readiness(
    *,
    autonomous_requested: bool,
    report: RuntimeCapabilityReport,
) -> ProductionReadinessDecision:
    """Fail closed when production dependencies are unavailable."""

    production_ready = bool(
        report.production_ready
    )

    return ProductionReadinessDecision(
        autonomous_requested=bool(
            autonomous_requested
        ),
        production_ready=production_ready,
        scheduler_enabled=(
            bool(
                autonomous_requested
            )
            and production_ready
        ),
        missing_required=tuple(
            report.missing_required
        ),
    )
