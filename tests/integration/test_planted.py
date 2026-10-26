"""Подсаженные случаи (задача 1.4): эталон №1 даёт число, посчитанное вручную, а неверные
варианты — другое число, то есть ловушки действительно ловят.

Каждый запрос выполняется дважды: на «только фоне» и на «фоне + подсаженных случаях».
Подсаженные строки не пересекаются с фоновыми, а запросы — суммы, поэтому разница двух
результатов зависит только от PLANTED_ORDERS (planted.py) и считается вручную.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import asyncpg
import pytest

from sql_helper.config import LLM_READONLY_ROLE, MIGRATOR_ROLE, DatabaseSettings
from sql_helper.infrastructure.seed.generator import Dataset, generate
from sql_helper.infrastructure.seed.loader import load
from sql_helper.infrastructure.seed.planted import add_planted

PLANTED_DB_NAME = "bookstore_planted_test"

# Эталонный запрос №1 (docs/bookstore_text2sql_context.md) дословно, проверен sql-reviewer
REFERENCE_MARCH = """
WITH revenue AS (
    SELECT
        o.id AS order_id,
        SUM(oi.unit_price * oi.quantity) - o.discount_per_order AS order_revenue
    FROM payments p
    JOIN orders o      ON o.id = p.order_id
    JOIN order_item oi ON oi.order_id = o.id
    WHERE p.paid_at >= '2026-03-01'
      AND p.paid_at <  '2026-04-01'
      AND p.status = 'succeeded'
      AND o.status = 'confirmed'
    GROUP BY o.id
),
march_refunds AS (
    SELECT COALESCE(SUM(r.quantity * oi.unit_price), 0) AS refunds_amount
    FROM refunds r
    JOIN order_item oi ON oi.id = r.order_item_id
    WHERE r.refunded_at >= '2026-03-01'
      AND r.refunded_at <  '2026-04-01'
)
SELECT
    (SELECT COALESCE(SUM(order_revenue), 0) FROM revenue)
  - (SELECT refunds_amount FROM march_refunds) AS march_revenue;
"""

# Экземпляры по авторам за март 2026, проверен sql-reviewer
COPIES_BY_AUTHOR_MARCH = """
WITH paid_orders AS (
    SELECT o.id
    FROM orders o
    JOIN payments p ON p.order_id = o.id
    WHERE o.status = 'confirmed'
      AND p.status = 'succeeded'
      AND p.paid_at >= '2026-03-01'
      AND p.paid_at <  '2026-04-01'
),
sold AS (
    SELECT oi.book_id, SUM(oi.quantity) AS qty
    FROM order_item oi
    JOIN paid_orders po ON po.id = oi.order_id
    GROUP BY oi.book_id
),
returned AS (
    SELECT oi.book_id, SUM(r.quantity) AS qty
    FROM refunds r
    JOIN order_item oi ON oi.id = r.order_item_id
    WHERE r.refunded_at >= '2026-03-01'
      AND r.refunded_at <  '2026-04-01'
    GROUP BY oi.book_id
),
copies AS (
    SELECT COALESCE(s.book_id, rt.book_id) AS book_id,
           COALESCE(s.qty, 0) - COALESCE(rt.qty, 0) AS qty
    FROM sold s
    FULL JOIN returned rt ON rt.book_id = s.book_id
)
SELECT a.id AS author_id, a.name, a.surname, SUM(c.qty) AS copies
FROM copies c
JOIN book_author ba ON ba.book_id = c.book_id
JOIN authors a      ON a.id = ba.author_id
GROUP BY a.id, a.name, a.surname
ORDER BY copies DESC;
"""


def _revenue(start: str, end: str) -> str:
    # Сначала метки, потом даты: две замены подряд для апреля сдвинули бы и начало
    # ('2026-03-01' → '2026-04-01' → '2026-05-01') — период стал бы пустым
    template = REFERENCE_MARCH.replace("'2026-03-01'", "{start}").replace("'2026-04-01'", "{end}")
    return template.replace("{start}", f"'{start}'").replace("{end}", f"'{end}'")


def _variant(sql: str, old: str, new: str) -> str:
    """Неверный вариант = эталон с одной правкой; правка обязана найтись в тексте."""
    assert old in sql, old
    return sql.replace(old, new)


PERIOD_BY_PAYMENT = """\
    WHERE p.paid_at >= '2026-03-01'
      AND p.paid_at <  '2026-04-01'
      AND p.status = 'succeeded'
"""
PERIOD_BY_ORDER = """\
    WHERE o.created_at >= '2026-03-01'
      AND o.created_at <  '2026-04-01'
"""

# Вклад подсаженных строк в выручку месяца, ₸ — посчитано вручную по PLANTED_ORDERS
EXPECTED_REVENUE = {
    # продажа случая 5: 2 × 2 000
    "2026-02": ("2026-02-01", "2026-03-01", Decimal(4000)),
    # случай 1: 6 000 + 2 000 − 1 000 = 7 000; случай 2: 2 000; случай 3: 0;
    # 23:50 31 марта: 2 000; книга двух авторов: 10 000; возврат февральской продажи: −2 000
    "2026-03": ("2026-03-01", "2026-04-01", Decimal(19000)),
    # 00:00 1 апреля: 3 000; возврат мартовского случая 1: −2 000
    "2026-04": ("2026-04-01", "2026-05-01", Decimal(1000)),
}

# Неверные варианты эталона за март и их вклад, посчитанный вручную (верный — 19 000)
WRONG_VARIANTS = {
    # Ловушка 1: скидка случая 1 вычитается на каждую из 2 позиций: 19 000 − 1 000
    "discount_per_item": (
        _variant(
            REFERENCE_MARCH,
            "SUM(oi.unit_price * oi.quantity) - o.discount_per_order",
            "SUM(oi.unit_price * oi.quantity - o.discount_per_order)",
        ),
        Decimal(18000),
    ),
    # Ловушка 2: «заказы марта» с любым платежом — заказ размножается на число платежей.
    # Случай 2 (failed + succeeded) — 2 × 2 000, случай 3 (failed + pending) — 2 × 3 000,
    # 00:00 1 апреля оформлен 31 марта — 3 000: 7 000 + 4 000 + 6 000 + 2 000 + 3 000
    # + 10 000 − 2 000
    "order_date_any_payment": (
        _variant(REFERENCE_MARCH, PERIOD_BY_PAYMENT, PERIOD_BY_ORDER),
        Decimal(30000),
    ),
    # Ловушка 3: только orders.status — случай 3 без оплаты входит (3 000), как и заказ,
    # оформленный 31 марта и оплаченный 1 апреля (3 000): 19 000 + 3 000 + 3 000
    "status_only": (
        _variant(
            _variant(REFERENCE_MARCH, PERIOD_BY_PAYMENT, PERIOD_BY_ORDER),
            "    FROM payments p\n    JOIN orders o      ON o.id = p.order_id\n",
            "    FROM orders o\n",
        ),
        Decimal(25000),
    ),
    # Ловушка 4: <= захватывает платёж ровно в 00:00 1 апреля: 19 000 + 3 000
    "inclusive_end": (
        _variant(REFERENCE_MARCH, "<  '2026-04-01'", "<= '2026-04-01'"),
        Decimal(22000),
    ),
}

# Ловушка 5: в ноябре 2024 продажи есть, возвратов нет — SUM по пустому набору даёт NULL
NOVEMBER_2024 = _revenue("2024-11-01", "2024-12-01")
NOVEMBER_2024_NO_COALESCE = _variant(
    NOVEMBER_2024,
    "COALESCE(SUM(r.quantity * oi.unit_price), 0)",
    "SUM(r.quantity * oi.unit_price)",
)

# При периоде по paid_at фильтр p.status ничего не меняет: CHECK в схеме допускает paid_at
# только у succeeded. Поэтому ловушка 2 ловит период по дате заказа, а не просто пропуск фильтра
NO_PAYMENT_STATUS = _variant(REFERENCE_MARCH, "      AND p.status = 'succeeded'\n", "")

SCALAR_QUERIES = {
    **{month: _revenue(start, end) for month, (start, end, _) in EXPECTED_REVENUE.items()},
    **{name: sql for name, (sql, _) in WRONG_VARIANTS.items()},
    "november_2024": NOVEMBER_2024,
    "november_2024_no_coalesce": NOVEMBER_2024_NO_COALESCE,
    "no_payment_status": NO_PAYMENT_STATUS,
}


@dataclass(frozen=True)
class Results:
    background: dict[str, Any]
    full: dict[str, Any]
    copies_by_author: dict[str, int]  # фамилия → экземпляры, фон + подсаженные

    def delta(self, name: str) -> Decimal:
        planted: Decimal = self.full[name] - self.background[name]
        return planted


async def _load_and_query(
    settings: DatabaseSettings, data: Dataset
) -> tuple[dict[str, Any], dict[str, int]]:
    conn = await asyncpg.connect(settings.dsn(MIGRATOR_ROLE))
    try:
        await load(conn, data)
    finally:
        await conn.close()

    # Под той же ролью, под которой будет работать SQL от LLM
    conn = await asyncpg.connect(settings.dsn(LLM_READONLY_ROLE))
    try:
        scalars = {name: await conn.fetchval(sql) for name, sql in SCALAR_QUERIES.items()}
        authors = await conn.fetch(COPIES_BY_AUTHOR_MARCH)
    finally:
        await conn.close()
    return scalars, {row["surname"]: row["copies"] for row in authors}


@pytest.fixture(scope="module")
def results(create_database: Callable[[str], DatabaseSettings]) -> Results:
    settings = create_database(PLANTED_DB_NAME)
    background = generate(seed=42)
    before, _ = asyncio.run(_load_and_query(settings, background))
    after, copies_by_author = asyncio.run(_load_and_query(settings, add_planted(background)))
    return Results(before, after, copies_by_author)


@pytest.mark.parametrize("month", EXPECTED_REVENUE)
def test_reference_query_matches_hand_count(results: Results, month: str) -> None:
    expected = EXPECTED_REVENUE[month][2]

    assert results.delta(month) == expected


@pytest.mark.parametrize("name", WRONG_VARIANTS)
def test_wrong_variant_gives_other_number(results: Results, name: str) -> None:
    expected_wrong = WRONG_VARIANTS[name][1]

    assert results.delta(name) == expected_wrong
    assert results.full[name] != results.full["2026-03"]


def test_month_without_refunds_needs_coalesce(results: Results) -> None:
    assert results.full["november_2024"] is not None
    assert results.full["november_2024_no_coalesce"] is None


def test_payment_status_filter_is_redundant_with_paid_at_period(results: Results) -> None:
    assert results.full["no_payment_status"] == results.full["2026-03"]


def test_two_author_book_counts_for_each_author(results: Results) -> None:
    # «Степные хроники»: продано 2 экземпляра — и по 2 у каждого из двух авторов,
    # так что сумма по авторам (4) больше проданного (2)
    assert results.copies_by_author["Сейткали"] == 2
    assert results.copies_by_author["Абенова"] == 2
