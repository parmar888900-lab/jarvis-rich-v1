"""Retry policy for autonomous production."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AutonomousRetryPolicy:
    """Control retries for transient autonomous failures."""

    max_attempts: int = 3
    base_delay_seconds: float = 5.0
    multiplier: float = 2.0
    max_delay_seconds: float = 60.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError(
                "max_attempts must be at least 1."
            )

        if self.base_delay_seconds < 0:
            raise ValueError(
                "base_delay_seconds cannot be negative."
            )

        if self.multiplier < 1:
            raise ValueError(
                "multiplier must be at least 1."
            )

        if self.max_delay_seconds < 0:
            raise ValueError(
                "max_delay_seconds cannot be negative."
            )

    def is_retryable_exception(
        self,
        exc: Exception,
    ) -> bool:
        """Return whether an exception is safely retryable."""

        return isinstance(
            exc,
            (
                TimeoutError,
                ConnectionError,
            ),
        )

    def delay_for_retry(
        self,
        retry_number: int,
    ) -> float:
        """Return delay before the specified retry.

        retry_number starts at 1 for the first retry.
        """

        if retry_number < 1:
            raise ValueError(
                "retry_number must be at least 1."
            )

        delay = (
            self.base_delay_seconds
            * (
                self.multiplier
                ** (retry_number - 1)
            )
        )

        return min(
            delay,
            self.max_delay_seconds,
        )
