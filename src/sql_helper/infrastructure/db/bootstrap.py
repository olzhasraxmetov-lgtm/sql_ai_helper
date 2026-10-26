"""Подготовка кластера до миграций: роли и права уровня базы (ADR 0004).

Роли живут на уровне кластера, а не базы, и создавать их может только суперпользователь,
поэтому это не миграция Alembic: миграции идут уже под ролью migrator.
Скрипт идемпотентен — запускается при каждом `docker compose up`.

Запуск: python -m sql_helper.infrastructure.db.bootstrap
"""

import asyncio

import asyncpg

from sql_helper.config import (
    APP_SERVICE_ROLE,
    LLM_READONLY_ROLE,
    MIGRATOR_ROLE,
    DatabaseSettings,
)


async def _upsert_login_role(conn: asyncpg.Connection, role: str, password: str) -> None:
    exists = await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", role)
    verb = "ALTER" if exists else "CREATE"
    # В DDL нельзя передать параметр, поэтому экранирование делает сам PostgreSQL через format()
    statement = await conn.fetchval(
        f"SELECT format('{verb} ROLE %I LOGIN PASSWORD %L', $1::text, $2::text)", role, password
    )
    await conn.execute(statement)


async def bootstrap(settings: DatabaseSettings) -> None:
    conn = await asyncpg.connect(settings.dsn(settings.admin_user))
    try:
        for role in (MIGRATOR_ROLE, APP_SERVICE_ROLE, LLM_READONLY_ROLE):
            await _upsert_login_role(conn, role, settings.password_for(role).get_secret_value())

        db = await conn.fetchval("SELECT quote_ident(current_database())")
        # Владелец базы может создавать в ней схемы; public в PG 15+ принадлежит владельцу базы,
        # там Alembic держит таблицу alembic_version
        await conn.execute(f"ALTER DATABASE {db} OWNER TO {MIGRATOR_ROLE}")
        # По умолчанию PUBLIC может создавать временные таблицы и читать схему public —
        # закрываем, чтобы llm_readonly видел из пользовательских объектов только shop
        await conn.execute(f"REVOKE TEMPORARY ON DATABASE {db} FROM PUBLIC")
        await conn.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        # Магазин работает по Asia/Almaty: литерал '2026-04-01' в SQL — полночь по Алматы,
        # а не по UTC (пояс образа postgres по умолчанию), иначе граница месяца съезжает на 5 часов
        await conn.execute(f"ALTER DATABASE {db} SET timezone = 'Asia/Almaty'")
        # Имена таблиц в SQL от LLM пишутся без схемы
        await conn.execute(f"ALTER ROLE {LLM_READONLY_ROLE} SET search_path = shop")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(bootstrap(DatabaseSettings()))
