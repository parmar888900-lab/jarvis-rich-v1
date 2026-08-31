"""Live health probes for production network providers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


@dataclass(frozen=True)
class ProviderHealth:
    """Result of one live provider health probe."""

    name: str
    available: bool
    detail: str


class ProviderHealthService:
    """Probe network providers with bounded timeouts."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 3.0,
    ) -> None:

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than zero."
            )

        self.timeout_seconds = float(
            timeout_seconds
        )

    def probe_ollama(
        self,
        *,
        base_url: str,
        model: str,
    ) -> ProviderHealth:
        """Require Ollama and the configured model."""

        url = (
            str(base_url).rstrip("/")
            + "/api/tags"
        )

        try:
            data = self._get_json(
                url
            )
        except Exception as exc:
            return self._failure(
                name="ollama",
                exc=exc,
            )

        models = data.get(
            "models"
        )

        if not isinstance(
            models,
            list,
        ):
            return ProviderHealth(
                name="ollama",
                available=False,
                detail=(
                    "invalid /api/tags response: "
                    "models list missing"
                ),
            )

        configured_model = str(
            model
        ).strip()

        names = {
            str(
                item.get(
                    "name",
                    "",
                )
            ).strip()
            for item
            in models
            if isinstance(
                item,
                dict,
            )
        }

        if configured_model not in names:
            return ProviderHealth(
                name="ollama",
                available=False,
                detail=(
                    "service reachable; configured "
                    f"model unavailable: {configured_model}"
                ),
            )

        return ProviderHealth(
            name="ollama",
            available=True,
            detail=(
                "service reachable; configured "
                f"model available: {configured_model}"
            ),
        )

    def probe_comfyui(
        self,
        *,
        base_url: str,
    ) -> ProviderHealth:
        """Require a valid ComfyUI system-stats response."""

        url = (
            str(base_url).rstrip("/")
            + "/system_stats"
        )

        try:
            data = self._get_json(
                url
            )
        except Exception as exc:
            return self._failure(
                name="comfyui",
                exc=exc,
            )

        system = data.get(
            "system"
        )

        devices = data.get(
            "devices"
        )

        if (
            not isinstance(
                system,
                dict,
            )
            or not isinstance(
                devices,
                list,
            )
        ):
            return ProviderHealth(
                name="comfyui",
                available=False,
                detail=(
                    "invalid /system_stats response"
                ),
            )

        return ProviderHealth(
            name="comfyui",
            available=True,
            detail=(
                "service reachable; "
                f"devices={len(devices)}"
            ),
        )

    def _get_json(
        self,
        url: str,
    ) -> dict:

        with urlopen(
            url,
            timeout=self.timeout_seconds,
        ) as response:

            status = getattr(
                response,
                "status",
                200,
            )

            if not (
                200
                <= int(status)
                < 300
            ):
                raise RuntimeError(
                    f"HTTP {status}"
                )

            body = response.read()

        data = json.loads(
            body.decode(
                "utf-8"
            )
        )

        if not isinstance(
            data,
            dict,
        ):
            raise ValueError(
                "provider response is not a JSON object"
            )

        return data

    @staticmethod
    def _failure(
        *,
        name: str,
        exc: Exception,
    ) -> ProviderHealth:

        if isinstance(
            exc,
            HTTPError,
        ):
            detail = (
                f"HTTP {exc.code}"
            )
        elif isinstance(
            exc,
            URLError,
        ):
            detail = (
                "unreachable: "
                f"{exc.reason}"
            )
        else:
            detail = (
                f"{type(exc).__name__}: {exc}"
            )

        return ProviderHealth(
            name=name,
            available=False,
            detail=detail,
        )
