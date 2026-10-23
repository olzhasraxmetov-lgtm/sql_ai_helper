"""Схема shop с таблицами магазина, пустая схема app, права ролей (ADR 0004)

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# asyncpg не выполняет несколько операторов в одном запросе — каждый оператор отдельной строкой
SCHEMAS = [
    "CREATE SCHEMA shop",
    "CREATE SCHEMA app",
]

# Порядок важен: таблица, на которую ссылаются, создаётся раньше той, что ссылается
SHOP_TABLES = [
    # ============ Справочники (без внешних ключей) ============
    """
    CREATE TABLE shop.genres (
        id   int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        name varchar(100) NOT NULL UNIQUE
    )
    """,
    """
    CREATE TABLE shop.authors (
        id      int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        name    varchar(100) NOT NULL,
        surname varchar(100) NOT NULL
    )
    """,
    """
    CREATE TABLE shop.users (
        id            int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        name          varchar(100) NOT NULL,
        surname       varchar(100) NOT NULL,
        birthdate     date,
        city          varchar(100),
        registered_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE shop.promocodes (
        id           int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        name         varchar(50) NOT NULL UNIQUE,
        discount_sum numeric(12, 2) NOT NULL CHECK (discount_sum > 0)
    )
    """,
    # ============ Каталог ============
    """
    CREATE TABLE shop.books (
        id       int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        title    varchar(255) NOT NULL,
        price    numeric(12, 2) NOT NULL CHECK (price >= 0),
        pages    int CHECK (pages > 0),
        genre_id int NOT NULL REFERENCES shop.genres (id)
    )
    """,
    # Первичный ключ — сама пара, поэтому дубль связи невозможен
    """
    CREATE TABLE shop.book_author (
        book_id   int NOT NULL REFERENCES shop.books (id),
        author_id int NOT NULL REFERENCES shop.authors (id),
        PRIMARY KEY (book_id, author_id)
    )
    """,
    # ============ Продажи ============
    """
    CREATE TABLE shop.orders (
        id                 int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        user_id            int NOT NULL REFERENCES shop.users (id),
        created_at         timestamptz NOT NULL DEFAULT now(),
        status             varchar(20) NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending', 'confirmed', 'cancelled')),
        promocode_id       int REFERENCES shop.promocodes (id),
        discount_per_order numeric(12, 2) NOT NULL DEFAULT 0 CHECK (discount_per_order >= 0),
        -- скидка без промокода невозможна
        CHECK (promocode_id IS NOT NULL OR discount_per_order = 0)
    )
    """,
    """
    CREATE TABLE shop.order_item (
        id         int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        order_id   int NOT NULL REFERENCES shop.orders (id),
        book_id    int NOT NULL REFERENCES shop.books (id),
        unit_price numeric(12, 2) NOT NULL CHECK (unit_price >= 0),
        quantity   int NOT NULL CHECK (quantity > 0),
        UNIQUE (order_id, book_id)
    )
    """,
    """
    CREATE TABLE shop.payments (
        id         int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        order_id   int NOT NULL REFERENCES shop.orders (id),
        status     varchar(20) NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending', 'succeeded', 'failed')),
        created_at timestamptz NOT NULL DEFAULT now(),
        paid_at    timestamptz,
        -- paid_at заполнен тогда и только тогда, когда платёж прошёл
        CHECK ((status = 'succeeded') = (paid_at IS NOT NULL))
    )
    """,
    # Не больше одного успешного платежа на заказ
    """
    CREATE UNIQUE INDEX uq_payments_one_succeeded_per_order
        ON shop.payments (order_id)
        WHERE status = 'succeeded'
    """,
    """
    CREATE TABLE shop.refunds (
        id            int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        order_item_id int NOT NULL REFERENCES shop.order_item (id),
        quantity      int NOT NULL CHECK (quantity > 0),
        reason        varchar(255),
        refunded_at   timestamptz NOT NULL DEFAULT now()
    )
    """,
    # PostgreSQL не создаёт индексы на внешние ключи сам — добавляем для частых JOIN
    "CREATE INDEX ix_books_genre_id ON shop.books (genre_id)",
    "CREATE INDEX ix_book_author_author_id ON shop.book_author (author_id)",
    "CREATE INDEX ix_orders_user_id ON shop.orders (user_id)",
    "CREATE INDEX ix_order_item_book_id ON shop.order_item (book_id)",
    "CREATE INDEX ix_payments_order_id ON shop.payments (order_id)",
    "CREATE INDEX ix_payments_paid_at ON shop.payments (paid_at)",
    "CREATE INDEX ix_refunds_order_item_id ON shop.refunds (order_item_id)",
    "CREATE INDEX ix_refunds_refunded_at ON shop.refunds (refunded_at)",
]

# Комментарии хранятся в базе, а не в SQL-файле: так они попадают в выгрузку pg_dump
COMMENTS = [
    "COMMENT ON COLUMN shop.users.birthdate IS 'Клиент может не указать'",
    "COMMENT ON COLUMN shop.promocodes.discount_sum IS 'Текущая скидка, ₸'",
    "COMMENT ON COLUMN shop.books.price IS 'Текущая цена в каталоге'",
    "COMMENT ON COLUMN shop.orders.promocode_id IS 'NULL = без промокода'",
    "COMMENT ON COLUMN shop.orders.discount_per_order IS 'Скидка, зафиксированная в заказе'",
    "COMMENT ON COLUMN shop.order_item.unit_price IS 'Цена за 1 шт. в момент заказа'",
    "COMMENT ON COLUMN shop.payments.created_at IS 'Начало попытки оплаты'",
    "COMMENT ON COLUMN shop.payments.paid_at IS 'Момент, когда деньги пришли'",
]

GRANTS = [
    # llm_readonly: только чтение shop. USAGE на app не выдаётся — схема для роли закрыта
    "GRANT USAGE ON SCHEMA shop TO llm_readonly",
    "GRANT SELECT ON ALL TABLES IN SCHEMA shop TO llm_readonly",
    # Таблицы, которые migrator создаст в shop позже, сразу доступны на чтение
    "ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA shop"
    " GRANT SELECT ON TABLES TO llm_readonly",
    # app_service: чтение и запись в app (таблиц пока нет — права на будущие)
    "GRANT USAGE ON SCHEMA app TO app_service",
    "ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA app"
    " GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_service",
    "ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA app"
    " GRANT USAGE, SELECT ON SEQUENCES TO app_service",
]


def upgrade() -> None:
    for statement in SCHEMAS + SHOP_TABLES + COMMENTS + GRANTS:
        op.execute(statement)


def downgrade() -> None:
    # Права по умолчанию для схемы удаляются вместе с ней
    op.execute("DROP SCHEMA app CASCADE")
    op.execute("DROP SCHEMA shop CASCADE")
