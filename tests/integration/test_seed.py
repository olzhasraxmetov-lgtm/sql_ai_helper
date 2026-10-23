"""Фоновые данные в базе: повторяемость, закономерности, правила уровня приложения."""

import asyncio
from collections.abc import Callable
from decimal import Decimal

import asyncpg
import pytest

from sql_helper.config import LLM_READONLY_ROLE, MIGRATOR_ROLE, DatabaseSettings
from sql_helper.infrastructure.seed.generator import generate
from sql_helper.infrastructure.seed.loader import load

SEED_DB_NAME = "bookstore_seed_test"

# Запросы проверены sql-reviewer; правила подсчёта — docs/sql-rules.md
MONTHLY_REVENUE = """
WITH paid_orders AS (
    SELECT o.id, o.discount_per_order,
           date_trunc('month', p.paid_at AT TIME ZONE 'Asia/Almaty') AS month
    FROM orders o
    JOIN payments p ON p.order_id = o.id AND p.status = 'succeeded'
    WHERE o.status = 'confirmed'
),
order_totals AS (
    SELECT po.month, sum(oi.unit_price * oi.quantity) - po.discount_per_order AS net
    FROM paid_orders po
    JOIN order_item oi ON oi.order_id = po.id
    GROUP BY po.id, po.month, po.discount_per_order
),
sales AS (
    SELECT month, sum(net) AS net FROM order_totals GROUP BY month
),
refunds_by_month AS (
    SELECT date_trunc('month', r.refunded_at AT TIME ZONE 'Asia/Almaty') AS month,
           sum(r.quantity * oi.unit_price) AS refunded
    FROM refunds r
    JOIN order_item oi ON oi.id = r.order_item_id
    JOIN paid_orders po ON po.id = oi.order_id
    GROUP BY 1
)
SELECT coalesce(s.month, r.month) AS month,
       coalesce(s.net, 0) - coalesce(r.refunded, 0) AS revenue
FROM sales s
FULL JOIN refunds_by_month r ON r.month = s.month
ORDER BY 1
"""

COPIES_BY_BOOK = """
WITH paid_orders AS (
    SELECT DISTINCT o.id
    FROM orders o
    JOIN payments p ON p.order_id = o.id AND p.status = 'succeeded'
    WHERE o.status = 'confirmed'
),
sold AS (
    SELECT oi.book_id, sum(oi.quantity) AS qty
    FROM order_item oi JOIN paid_orders po ON po.id = oi.order_id
    GROUP BY oi.book_id
),
returned AS (
    SELECT oi.book_id, sum(r.quantity) AS qty
    FROM refunds r
    JOIN order_item oi ON oi.id = r.order_item_id
    JOIN paid_orders po ON po.id = oi.order_id
    GROUP BY oi.book_id
)
SELECT s.book_id, s.qty - coalesce(rt.qty, 0) AS copies
FROM sold s LEFT JOIN returned rt ON rt.book_id = s.book_id
ORDER BY copies DESC
"""

REPEAT_BUYERS = """
SELECT count(*) AS repeat_buyers
FROM (
    SELECT o.user_id
    FROM orders o
    WHERE o.status = 'confirmed'
      AND EXISTS (SELECT 1 FROM payments p WHERE p.order_id = o.id AND p.status = 'succeeded')
    GROUP BY o.user_id
    HAVING count(*) >= 2
) AS t
"""

TOTALS = """
SELECT (SELECT count(*) FROM orders) AS orders,
       (SELECT sum(unit_price * quantity) FROM order_item) AS items_sum,
       (SELECT count(*) FROM refunds) AS refunds
"""


async def _seed(settings: DatabaseSettings, seed: int) -> None:
    conn = await asyncpg.connect(settings.dsn(MIGRATOR_ROLE))
    try:
        await load(conn, generate(seed))
    finally:
        await conn.close()


@pytest.fixture(scope="module")
def seeded(create_database: Callable[[str], DatabaseSettings]) -> DatabaseSettings:
    settings = create_database(SEED_DB_NAME)
    asyncio.run(_seed(settings, seed=42))
    return settings


async def _query(settings: DatabaseSettings, sql: str) -> list[asyncpg.Record]:
    # Проверки идут под той же ролью, под которой будет работать SQL от LLM
    conn = await asyncpg.connect(settings.dsn(LLM_READONLY_ROLE))
    try:
        return await conn.fetch(sql)
    finally:
        await conn.close()


async def test_reseed_with_same_seed_gives_same_totals(seeded: DatabaseSettings) -> None:
    first = await _query(seeded, TOTALS)

    await _seed(seeded, seed=42)  # повторный запуск: очистка и заполнение заново
    second = await _query(seeded, TOTALS)

    assert first == second
    assert first[0]["orders"] == 10_000


async def test_september_and_december_above_average_month(seeded: DatabaseSettings) -> None:
    rows = await _query(seeded, MONTHLY_REVENUE)
    revenue = {row["month"].strftime("%Y-%m"): row["revenue"] for row in rows}
    average = sum(revenue.values(), Decimal(0)) / len(revenue)

    peaks = {month: value for month, value in revenue.items() if month[5:] in ("09", "12")}

    assert set(peaks) == {"2024-12", "2025-09", "2025-12", "2026-09"}
    assert all(value > average for value in peaks.values()), (peaks, average)


async def test_top_fifth_of_books_give_most_copies(seeded: DatabaseSettings) -> None:
    rows = await _query(seeded, COPIES_BY_BOOK)
    copies = [row["copies"] for row in rows]  # по убыванию

    top = sum(copies[: 300 // 5])

    assert top > sum(copies) / 2


async def test_there_are_repeat_buyers(seeded: DatabaseSettings) -> None:
    rows = await _query(seeded, REPEAT_BUYERS)

    assert rows[0]["repeat_buyers"] > 0


async def test_application_rules_hold_in_database(seeded: DatabaseSettings) -> None:
    discount_over_sum = await _query(
        seeded,
        """
        SELECT o.id FROM orders o JOIN order_item oi ON oi.order_id = o.id
        GROUP BY o.id HAVING max(o.discount_per_order) > sum(oi.unit_price * oi.quantity)
        """,
    )
    refunded_over_bought = await _query(
        seeded,
        """
        SELECT oi.id FROM order_item oi JOIN refunds r ON r.order_item_id = oi.id
        GROUP BY oi.id HAVING sum(r.quantity) > max(oi.quantity)
        """,
    )

    assert discount_over_sum == []
    assert refunded_over_bought == []


async def test_next_insert_does_not_collide_with_loaded_ids(seeded: DatabaseSettings) -> None:
    conn = await asyncpg.connect(seeded.dsn(MIGRATOR_ROLE))
    transaction = conn.transaction()
    await transaction.start()
    try:
        loaded = await conn.fetchval("SELECT max(id) FROM shop.genres")
        new_id = await conn.fetchval("INSERT INTO shop.genres (name) VALUES ('Новый') RETURNING id")
    finally:
        await transaction.rollback()
        await conn.close()

    assert new_id == loaded + 1
