import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():

    with tempfile.TemporaryDirectory() as temp:

        database_path = (
            Path(temp)
            / "jarvis-cloud-test.db"
        )

        database_url = (
            "sqlite+aiosqlite:///"
            + database_path.as_posix()
        )

        env = os.environ.copy()

        env["DATABASE_URL"] = database_url
        env["JARVIS_DATABASE_URL"] = database_url

        code = r"""
import asyncio

from backend.config import settings
from backend.database import engine, init_db
from backend.services.runtime import RuntimeConfig


async def main():

    runtime = RuntimeConfig.from_environment()

    print(
        "SETTINGS_DATABASE_URL:",
        settings.database_url,
    )

    print(
        "RUNTIME_DATABASE_URL:",
        runtime.database_url,
    )

    print(
        "ENGINE_URL:",
        str(engine.url),
    )

    assert (
        settings.database_url
        == runtime.database_url
    )

    assert (
        str(engine.url)
        == settings.database_url
    )

    await init_db()

    await engine.dispose()

    print(
        "PASS: environment override controls "
        "the real SQLAlchemy engine."
    )


asyncio.run(main())
"""

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                code,
            ],
            env=env,
            text=True,
            capture_output=True,
        )

        print(result.stdout)

        if result.stderr:
            print(
                result.stderr,
                file=sys.stderr,
            )

        if result.returncode != 0:
            raise RuntimeError(
                "Child database test failed."
            )

        if not database_path.exists():
            raise RuntimeError(
                "Configured SQLite database "
                "was not created."
            )

        print(
            "PASS: SQLite database created "
            "at environment-configured path."
        )

        print()
        print(
            "PASS: cloud database binding "
            "regression complete."
        )


if __name__ == "__main__":
    main()
