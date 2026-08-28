import hashlib
from pathlib import Path


class ImageCache:

    def __init__(self):

        self.cache = Path("generated/images/cache")

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