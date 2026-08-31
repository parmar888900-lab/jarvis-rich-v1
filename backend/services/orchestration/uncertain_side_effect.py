"""Exceptions for externally uncertain side effects."""


class UncertainSideEffectError(RuntimeError):
    """Raised when an external side effect may have occurred.

    This error means the caller cannot safely conclude
    that the provider rejected or completed the operation.
    The persistent operation must therefore enter
    reconciliation-required state instead of being retried.
    """
