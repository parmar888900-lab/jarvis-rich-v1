"""Authentication for remote Jarvis command access."""

from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException, status


TOKEN_ENV = "JARVIS_REMOTE_TOKEN"


def require_remote_token(
    authorization: str | None = Header(default=None),
) -> None:
    """Require a valid Bearer token for remote command access."""

    expected = os.getenv(TOKEN_ENV, "").strip()

    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Remote command authentication is not configured.",
        )

    prefix = "Bearer "

    if (
        authorization is None
        or not authorization.startswith(prefix)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    supplied = authorization[len(prefix):].strip()

    if not supplied or not hmac.compare_digest(
        supplied,
        expected,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization.",
            headers={"WWW-Authenticate": "Bearer"},
        )
