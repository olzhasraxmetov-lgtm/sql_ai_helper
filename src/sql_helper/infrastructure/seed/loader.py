"""Запись Dataset в схему shop через COPY (ADR 0003)."""

from dataclasses import fields

import asyncpg

from sql_helper.infrastructure.seed.generator import Dataset

# Порядок загрузки: таблица, на которую ссылаются, — раньше той, что ссылается.
# Имена полей Dataset совпадают с именами таблиц.
TABLES = [field.name for field in fields(Dataset)]
TABLES_WITHOUT_IDENTITY = {"book_author"}


async def load(conn: asyncpg.Connection, data: Dataset) -> None:
    """Очищает таблицы shop и заполняет их заново — одной транзакцией."""
    async with conn.transaction():
        # Без CASCADE: если появится новая таблица со ссылкой на эти, TRUNCATE упадёт,
        # а не очистит её молча
        await conn.execute(f"TRUNCATE {', '.join(f'shop.{t}' for t in TABLES)} RESTART IDENTITY")
        for table in TABLES:
            rows = getattr(data, table)
            if not rows:
                continue
            # COPY пишет id как есть даже в GENERATED ALWAYS — id нужны заранее для внешних ключей
            await conn.copy_records_to_table(
                table, schema_name="shop", records=rows, columns=list(rows[0]._fields)
            )
        # Иначе следующий обычный INSERT получит id = 1 и упрётся в первичный ключ
        for table in TABLES:
            if table in TABLES_WITHOUT_IDENTITY:
                continue
            await conn.execute(
                f"SELECT setval(pg_get_serial_sequence('shop.{table}', 'id'), max(id))"
                f" FROM shop.{table} HAVING count(*) > 0"
            )
