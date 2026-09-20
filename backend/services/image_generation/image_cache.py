import hashlib
from pathlib import Path

from backend.services.runtime.runtime_config import RuntimeConfig


class ImageCache:

    def __init__(
        self,
        runtime_config: RuntimeConfig | None = None,
    ):
        config = (
            runtime_config
            if runtime_config is not None
            else RuntimeConfig.from_environment()
        )

        self.cache = (
            Path(config.generated_dir)
            / "images"
            / "cache"
        )

        self.cache.mkdir(
            parents=True,
            exist_ok=True,
        )

    def filename(
        self,
        prompt: str,
    ) -> Path:

        key = hashlib.md5(
            prompt.encode()
        ).hexdigest()

        return self.cache / f"{key}.png"
