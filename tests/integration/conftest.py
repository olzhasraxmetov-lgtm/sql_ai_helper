"""Тесты на настоящем PostgreSQL: отдельная база, роли и миграции как в docker compose.

Нужен запущенный PostgreSQL (`docker compose up -d db`) и переменные DB_* (см. .env.example).
Без базы тесты пропускаются локально, но падают в CI — там база обязана быть.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import NoReturn

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError

from sql_helper.config import MIGRATOR_ROLE, DatabaseSettings
from sql_helper.infrastructure.db.bootstrap import bootstrap

ROOT = Path(__file__).resolve().parents[2]
TEST_DB_NAME = "bookstore_test"

type Connect = Callable[[str], Awaitable[asyncpg.Connection]]


def _unavailable(reason: str) -> NoReturn:
    if os.environ.get("CI"):
        pytest.fail(f"PostgreSQL недоступен в CI: {reason}")
    pytest.skip(f"PostgreSQL недоступен: {reason}")


async def _recreate_database(settings: DatabaseSettings) -> None:
    maintenance = settings.model_copy(update={"name": "postgres"})
    conn = await asyncpg.connect(maintenance.dsn(settings.admin_user))
    try:
        await conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)")
        await conn.execute(f"CREATE DATABASE {TEST_DB_NAME}")
    finally:
        await conn.close()


@pytest.fixture(scope="session")
def db_settings() -> DatabaseSettings:
    """Пустая база bookstore_test: bootstrap ролей и все миграции."""
    try:
        base = DatabaseSettings()
    except ValidationError as error:
        _unavailable(f"не заданы переменные DB_*: {error}")
    settings = base.model_copy(update={"name": TEST_DB_NAME})
    try:
        asyncio.run(_recreate_database(settings))
    except (OSError, asyncpg.PostgresError) as error:
        _unavailable(str(error))

    asyncio.run(bootstrap(settings))
    alembic_config = Config(ROOT / "alembic.ini")
    alembic_config.set_main_option(
        "sqlalchemy.url", settings.dsn(MIGRATOR_ROLE, driver="postgresql+asyncpg")
    )
    alembic_config.attributes["configure_logger"] = False
    command.upgrade(alembic_config, "head")
    return settings


@pytest.fixture
async def connect(db_settings: DatabaseSettings) -> AsyncIterator[Connect]:
    """Открывает соединения под нужной ролью и закрывает их после теста."""
    opened: list[asyncpg.Connection] = []

    async def _connect(role: str) -> asyncpg.Connection:
        conn = await asyncpg.connect(db_settings.dsn(role))
        opened.append(conn)
        return conn

    yield _connect
    for conn in opened:
        await conn.close()
