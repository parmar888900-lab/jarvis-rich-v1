"""Runtime capability detection for autonomous Jarvis production."""

from __future__ import annotations

import importlib.util
import shutil
from dataclasses import dataclass
from pathlib import Path

from backend.services.runtime.runtime_config import (
    RuntimeConfig,
)
from backend.services.runtime.provider_health import (
    ProviderHealthService,
)


@dataclass(frozen=True)
class Capability:
    """Availability of one runtime dependency."""

    name: str
    available: bool
    required_for_production: bool
    detail: str


@dataclass(frozen=True)
class RuntimeCapabilityReport:
    """Complete execution capability report."""

    capabilities: tuple[
        Capability,
        ...
    ]

    @property
    def production_ready(
        self,
    ) -> bool:
        return all(
            item.available
            for item
            in self.capabilities
            if item.required_for_production
        )

    @property
    def missing_required(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            item.name
            for item
            in self.capabilities
            if (
                item.required_for_production
                and not item.available
            )
        )

    def as_dict(
        self,
    ) -> dict:
        return {
            "production_ready":
                self.production_ready,
            "missing_required":
                list(
                    self.missing_required
                ),
            "capabilities": [
                {
                    "name": item.name,
                    "available":
                        item.available,
                    "required_for_production":
                        item.required_for_production,
                    "detail": item.detail,
                }
                for item
                in self.capabilities
            ],
        }


class RuntimeCapabilityService:
    """Inspect whether this machine can execute Jarvis production."""

    def __init__(
        self,
        config: RuntimeConfig | None = None,
    ) -> None:
        self.config = (
            config
            if config is not None
            else RuntimeConfig.from_environment()
        )

    def inspect(
        self,
    ) -> RuntimeCapabilityReport:
        """Perform local, non-network capability checks."""

        config = self.config

        capabilities = (
            self._configured_url(
                name="ollama",
                value=config.ollama_base_url,
                required=True,
            ),
            self._configured_text(
                name="ollama_model",
                value=config.ollama_model,
                required=True,
            ),
            self._configured_url(
                name="comfyui",
                value=config.comfyui_url,
                required=True,
            ),
            self._directory(
                name="comfyui_output_dir",
                path=config.comfyui_output_dir,
                required=True,
            ),
            self._file(
                name="flux_workflow",
                path=config.flux_workflow_path,
                required=True,
            ),
            self._file_or_command(
                name="piper_executable",
                value=config.piper_executable,
                required=True,
            ),
            self._file(
                name="piper_model",
                path=config.piper_model_path,
                required=True,
            ),
            self._python_module(
                name="whisper",
                module="whisper",
                required=True,
            ),
            self._command(
                name="ffmpeg",
                command=config.ffmpeg_executable,
                required=True,
            ),
            self._directory_or_creatable(
                name="generated_storage",
                path=config.generated_dir,
                required=True,
            ),
            self._database(
                config.database_url
            ),
            self._file(
                name="youtube_token",
                path=config.youtube_token_path,
                required=True,
            ),
            self._file(
                name="youtube_client_secret",
                path=config.youtube_client_secret_path,
                required=False,
            ),
        )

        return RuntimeCapabilityReport(
            capabilities=capabilities
        )

    def inspect_live(
        self,
        *,
        timeout_seconds: float = 3.0,
    ) -> RuntimeCapabilityReport:
        """Combine static checks with bounded live provider probes."""

        static_report = self.inspect()

        health = ProviderHealthService(
            timeout_seconds=timeout_seconds
        )

        ollama = health.probe_ollama(
            base_url=self.config.ollama_base_url,
            model=self.config.ollama_model,
        )

        comfyui = health.probe_comfyui(
            base_url=self.config.comfyui_url,
        )

        live_by_name = {
            ollama.name: ollama,
            comfyui.name: comfyui,
        }

        capabilities = tuple(
            Capability(
                name=item.name,
                available=(
                    live_by_name[item.name].available
                    if item.name in live_by_name
                    else item.available
                ),
                required_for_production=(
                    item.required_for_production
                ),
                detail=(
                    live_by_name[item.name].detail
                    if item.name in live_by_name
                    else item.detail
                ),
            )
            for item
            in static_report.capabilities
        )

        return RuntimeCapabilityReport(
            capabilities=capabilities
        )

    @staticmethod
    def _configured_text(
        *,
        name: str,
        value: str,
        required: bool,
    ) -> Capability:
        available = bool(
            str(
                value
            ).strip()
        )

        return Capability(
            name=name,
            available=available,
            required_for_production=required,
            detail=(
                str(value)
                if available
                else "not configured"
            ),
        )

    @staticmethod
    def _configured_url(
        *,
        name: str,
        value: str,
        required: bool,
    ) -> Capability:
        text = str(
            value
        ).strip()

        available = (
            text.startswith(
                "http://"
            )
            or text.startswith(
                "https://"
            )
        )

        return Capability(
            name=name,
            available=available,
            required_for_production=required,
            detail=(
                text
                if available
                else "invalid or missing URL"
            ),
        )

    @staticmethod
    def _file(
        *,
        name: str,
        path: Path,
        required: bool,
    ) -> Capability:
        resolved = Path(
            path
        )

        return Capability(
            name=name,
            available=resolved.is_file(),
            required_for_production=required,
            detail=str(
                resolved
            ),
        )

    @staticmethod
    def _directory(
        *,
        name: str,
        path: Path,
        required: bool,
    ) -> Capability:
        resolved = Path(
            path
        )

        return Capability(
            name=name,
            available=resolved.is_dir(),
            required_for_production=required,
            detail=str(
                resolved
            ),
        )

    @staticmethod
    def _directory_or_creatable(
        *,
        name: str,
        path: Path,
        required: bool,
    ) -> Capability:
        resolved = Path(
            path
        )

        if resolved.exists():
            available = (
                resolved.is_dir()
            )
        else:
            parent = (
                resolved.parent
                if resolved.parent
                != Path("")
                else Path(".")
            )

            available = (
                parent.exists()
                and parent.is_dir()
            )

        return Capability(
            name=name,
            available=available,
            required_for_production=required,
            detail=str(
                resolved
            ),
        )

    @staticmethod
    def _command(
        *,
        name: str,
        command: str,
        required: bool,
    ) -> Capability:
        resolved = shutil.which(
            str(
                command
            )
        )

        return Capability(
            name=name,
            available=(
                resolved is not None
            ),
            required_for_production=required,
            detail=(
                resolved
                if resolved is not None
                else (
                    f"command not found: "
                    f"{command}"
                )
            ),
        )

    @staticmethod
    def _file_or_command(
        *,
        name: str,
        value: Path,
        required: bool,
    ) -> Capability:
        path = Path(
            value
        )

        if path.is_file():
            return Capability(
                name=name,
                available=True,
                required_for_production=required,
                detail=str(
                    path
                ),
            )

        resolved = shutil.which(
            str(
                value
            )
        )

        return Capability(
            name=name,
            available=(
                resolved is not None
            ),
            required_for_production=required,
            detail=(
                resolved
                if resolved is not None
                else str(
                    path
                )
            ),
        )

    @staticmethod
    def _python_module(
        *,
        name: str,
        module: str,
        required: bool,
    ) -> Capability:
        available = (
            importlib.util.find_spec(
                module
            )
            is not None
        )

        return Capability(
            name=name,
            available=available,
            required_for_production=required,
            detail=(
                f"python module: {module}"
            ),
        )

    @staticmethod
    def _database(
        configured_url: str,
    ) -> Capability:
        url = str(
            configured_url
        ).strip()

        if url:
            return Capability(
                name="database",
                available=True,
                required_for_production=True,
                detail=url,
            )

        # The application currently has its own
        # SQLite default in backend.config.
        return Capability(
            name="database",
            available=True,
            required_for_production=True,
            detail=(
                "application default database "
                "configuration"
            ),
        )
