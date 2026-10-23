"""Права ролей (ADR 0004): SQL от LLM видит только shop и только на чтение."""

import asyncpg
import pytest

from sql_helper.config import APP_SERVICE_ROLE, LLM_READONLY_ROLE, MIGRATOR_ROLE

from .conftest import Connect


async def test_llm_readonly_reads_shop_without_schema_prefix(connect: Connect) -> None:
    conn = await connect(LLM_READONLY_ROLE)

    # Имя без схемы — проверяет и SELECT, и search_path = shop
    count = await conn.fetchval("SELECT count(*) FROM books")

    assert count == 0


async def test_llm_readonly_cannot_read_app(connect: Connect) -> None:
    migrator = await connect(MIGRATOR_ROLE)
    await migrator.execute("CREATE TABLE IF NOT EXISTS app.probe (id int)")
    conn = await connect(LLM_READONLY_ROLE)

    with pytest.raises(
        asyncpg.InsufficientPrivilegeError, match="permission denied for schema app"
    ):
        await conn.fetch("SELECT * FROM app.probe")


async def test_llm_readonly_cannot_insert_into_shop(connect: Connect) -> None:
    conn = await connect(LLM_READONLY_ROLE)

    with pytest.raises(asyncpg.InsufficientPrivilegeError, match="permission denied for table"):
        await conn.execute("INSERT INTO genres (name) VALUES ('Хакерская')")


async def test_llm_readonly_cannot_read_alembic_version(connect: Connect) -> None:
    conn = await connect(LLM_READONLY_ROLE)

    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await conn.fetch("SELECT * FROM public.alembic_version")


async def test_new_shop_table_is_readable_by_llm_readonly(connect: Connect) -> None:
    migrator = await connect(MIGRATOR_ROLE)
    await migrator.execute("CREATE TABLE IF NOT EXISTS shop.added_later (id int)")
    conn = await connect(LLM_READONLY_ROLE)

    rows = await conn.fetch("SELECT * FROM added_later")

    assert rows == []


async def test_app_service_writes_to_app(connect: Connect) -> None:
    migrator = await connect(MIGRATOR_ROLE)
    await migrator.execute(
        "CREATE TABLE IF NOT EXISTS app.journal_probe"
        " (id int GENERATED ALWAYS AS IDENTITY PRIMARY KEY, note text)"
    )
    conn = await connect(APP_SERVICE_ROLE)

    new_id = await conn.fetchval("INSERT INTO app.journal_probe (note) VALUES ('ok') RETURNING id")

    assert new_id is not None


async def test_app_service_cannot_write_to_shop(connect: Connect) -> None:
    conn = await connect(APP_SERVICE_ROLE)

    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await conn.execute("INSERT INTO shop.genres (name) VALUES ('Чужая')")
