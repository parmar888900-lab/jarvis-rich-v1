import asyncio

from sqlalchemy import inspect

from backend.database import (
    engine,
    init_db,
)


async def main():
    await init_db()

    async with engine.connect() as conn:
        tables = await conn.run_sync(
            lambda sync_conn: inspect(
                sync_conn
            ).get_table_names()
        )

    print("DATABASE TABLES:")
    for table in tables:
        print("-", table)

    assert "goals" in tables

    await engine.dispose()

    print()
    print(
        "PASS: goals table registered "
        "in Jarvis database."
    )


asyncio.run(main())
