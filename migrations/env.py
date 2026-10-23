"""Окружение Alembic: миграции пишутся на чистом SQL, моделей и autogenerate нет (ADR 0003)."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from sql_helper.config import MIGRATOR_ROLE, DatabaseSettings

config = context.config

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)


def _url() -> str:
    # Тесты передают URL своей базы; в остальных случаях — из переменных DB_*
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    return DatabaseSettings().dsn(MIGRATOR_ROLE, driver="postgresql+asyncpg")


def _run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, transaction_per_migration=True)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    engine = create_async_engine(_url())
    async with engine.connect() as connection:
        await connection.run_sync(_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Офлайн-режим не поддерживается: миграции применяются к живой базе")

asyncio.run(_run_async())
