"""Minimal management CLI.

Usage:
    python -m app.cli createsuperuser <email> [password]
"""

import asyncio
import getpass
import sys

from fastapi_users.db import SQLAlchemyUserDatabase

from app.core.db import async_session_maker
from app.features.users.manager import UserManager
from app.features.users.models import User
from app.features.users.schemas import UserCreate
from app.features.users.security import password_helper


async def create_superuser(email: str, password: str) -> None:
    async with async_session_maker() as session:
        user_db: SQLAlchemyUserDatabase = SQLAlchemyUserDatabase(session, User)
        manager = UserManager(user_db, password_helper)
        user = await manager.create(
            UserCreate(
                email=email,
                password=password,
                is_superuser=True,
                is_verified=True,
            )
        )
        print(f"Created superuser {user.email} ({user.id})")


def main() -> None:
    if len(sys.argv) < 3 or sys.argv[1] != "createsuperuser":
        print(__doc__)
        raise SystemExit(1)
    email = sys.argv[2]
    password = sys.argv[3] if len(sys.argv) > 3 else getpass.getpass("Password: ")
    asyncio.run(create_superuser(email, password))


if __name__ == "__main__":
    main()
