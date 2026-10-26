"""Заполняет shop фоновыми данными и подсаженными случаями.

Повторный запуск очищает и заполняет заново.

Запуск в Docker: docker compose run --rm migrate python -m sql_helper.infrastructure.seed
С хоста (нужен .env с DB_*): uv run python -m sql_helper.infrastructure.seed [--seed 42]
"""

import argparse
import asyncio

import asyncpg

from sql_helper.config import MIGRATOR_ROLE, DatabaseSettings
from sql_helper.infrastructure.seed.generator import DEFAULT_SEED, generate
from sql_helper.infrastructure.seed.loader import TABLES, load
from sql_helper.infrastructure.seed.planted import add_planted


async def main(seed: int) -> None:
    data = add_planted(generate(seed))
    # Пишет владелец таблиц: llm_readonly и app_service в shop писать не могут
    conn = await asyncpg.connect(DatabaseSettings().dsn(MIGRATOR_ROLE))
    try:
        await load(conn, data)
    finally:
        await conn.close()
    counts = ", ".join(f"{table}={len(getattr(data, table))}" for table in TABLES)
    print(f"seed={seed}: {counts}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Заполнить shop фоновыми данными и подсаженными случаями"
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    asyncio.run(main(parser.parse_args().seed))
