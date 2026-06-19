"""Block until the database accepts connections (used by the entrypoint)."""
import asyncio
import sys

from sqlalchemy import text

from app.core.db import engine

ATTEMPTS = 60


async def main() -> None:
    for attempt in range(1, ATTEMPTS + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            print("Database ready.")
            await engine.dispose()
            return
        except Exception as exc:  # noqa: BLE001 - retry on any connection error
            print(f"Database not ready ({attempt}/{ATTEMPTS}): {exc}")
            await asyncio.sleep(1)
    print("Database never became ready; giving up.")
    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
