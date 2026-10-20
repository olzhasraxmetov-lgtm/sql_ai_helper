-- Схема книжного магазина (PostgreSQL), v1
-- Порядок важен: таблица, на которую ссылаются, создаётся раньше той, что ссылается.

-- ============ Справочники (без внешних ключей) ============

CREATE TABLE genres (
    id   int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name varchar(100) NOT NULL UNIQUE
);

CREATE TABLE authors (
    id      int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name    varchar(100) NOT NULL,
    surname varchar(100) NOT NULL
);

CREATE TABLE users (
    id            int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name          varchar(100) NOT NULL,
    surname       varchar(100) NOT NULL,
    birthdate     date,                          -- клиент может не указать
    city          varchar(100),
    registered_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE promocodes (
    id           int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name         varchar(50) NOT NULL UNIQUE,
    discount_sum numeric(12, 2) NOT NULL CHECK (discount_sum > 0)  -- текущая скидка, ₸
);

-- ============ Каталог ============

CREATE TABLE books (
    id       int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title    varchar(255) NOT NULL,
    price    numeric(12, 2) NOT NULL CHECK (price >= 0),        -- текущая цена в каталоге
    pages    int CHECK (pages > 0),
    genre_id int NOT NULL REFERENCES genres (id)
);

-- Таблица связи: первичный ключ — сама пара, поэтому дубль связи невозможен
CREATE TABLE book_author (
    book_id   int NOT NULL REFERENCES books (id),
    author_id int NOT NULL REFERENCES authors (id),
    PRIMARY KEY (book_id, author_id)
);

-- ============ Продажи ============

CREATE TABLE orders (
    id                        int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id                   int NOT NULL REFERENCES users (id),
    created_at                timestamptz NOT NULL DEFAULT now(),
    status                    varchar(20) NOT NULL DEFAULT 'pending'
                              CHECK (status IN ('pending', 'confirmed', 'cancelled')),
    promocode_id              int REFERENCES promocodes (id),          -- NULL = без промокода
    discount_per_order        numeric(12, 2) NOT NULL DEFAULT 0       -- скидка, зафиксированная в заказе
                              CHECK (discount_per_order >= 0),
    -- скидка без промокода невозможна
    CHECK (promocode_id IS NOT NULL OR discount_per_order = 0)
);

CREATE TABLE order_item (
    id         int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id   int NOT NULL REFERENCES orders (id),
    book_id    int NOT NULL REFERENCES books (id),
    unit_price numeric(12, 2) NOT NULL CHECK (unit_price >= 0),   -- цена за 1 шт. в момент заказа
    quantity   int NOT NULL CHECK (quantity > 0),
    UNIQUE (order_id, book_id)                                    -- одна книга = одна позиция
);

CREATE TABLE payments (
    id         int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id   int NOT NULL REFERENCES orders (id),
    status     varchar(20) NOT NULL DEFAULT 'pending'
               CHECK (status IN ('pending', 'succeeded', 'failed')),
    created_at timestamptz NOT NULL DEFAULT now(),  -- начало попытки оплаты
    paid_at    timestamptz,                         -- момент, когда деньги пришли
    -- paid_at заполнен тогда и только тогда, когда платёж прошёл
    CHECK ((status = 'succeeded') = (paid_at IS NOT NULL))
);

-- Не больше одного успешного платежа на заказ (частичный уникальный индекс)
CREATE UNIQUE INDEX uq_payments_one_succeeded_per_order
    ON payments (order_id)
    WHERE status = 'succeeded';

CREATE TABLE refunds (
    id            int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_item_id int NOT NULL REFERENCES order_item (id),
    quantity      int NOT NULL CHECK (quantity > 0),
    reason        varchar(255),
    refunded_at   timestamptz NOT NULL DEFAULT now()
);

-- ============ Индексы ============
-- PostgreSQL не создаёт индексы на внешние ключи сам — добавляем для частых JOIN
CREATE INDEX ix_books_genre_id         ON books (genre_id);
CREATE INDEX ix_book_author_author_id  ON book_author (author_id);
CREATE INDEX ix_orders_user_id         ON orders (user_id);
CREATE INDEX ix_order_item_book_id     ON order_item (book_id);
CREATE INDEX ix_payments_order_id      ON payments (order_id);
CREATE INDEX ix_payments_paid_at       ON payments (paid_at);
CREATE INDEX ix_refunds_order_item_id  ON refunds (order_item_id);
CREATE INDEX ix_refunds_refunded_at    ON refunds (refunded_at);
