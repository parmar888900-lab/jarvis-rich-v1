"""Regression test for analytics model registration in init_db."""

import asyncio
import tempfile
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import (
    create_async_engine,
)

from backend.database import Base

# Import exactly as init_db registration does.
from backend.models import (
    agent,
    command,
    conversation,
    goal,
    memory,
    production_cycle,
    production_operation,
    youtube_performance_snapshot,
)


async def main():
    print("=" * 72)
    print("ANALYTICS MODEL REGISTRATION TEST")
    print("=" * 72)

    with tempfile.TemporaryDirectory() as directory:
        database_path = (
            Path(directory)
            / "registration.db"
        )

        engine = create_async_engine(
            "sqlite+aiosqlite:///"
            f"{database_path}"
        )

        async with engine.begin() as connection:
            await connection.run_sync(
                Base.metadata.create_all
            )

            tables = await connection.run_sync(
                lambda sync_connection: (
                    inspect(
                        sync_connection
                    ).get_table_names()
                )
            )

        await engine.dispose()

        assert (
            "youtube_performance_snapshots"
            in tables
        )

        print(
            "PASS: analytics snapshot model "
            "is registered with Base metadata."
        )

        print(
            "PASS: youtube_performance_snapshots "
            "table can be created."
        )

    print("=" * 72)
    print(
        "ALL ANALYTICS MODEL REGISTRATION "
        "TESTS PASSED"
    )
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(
        main()
    )
