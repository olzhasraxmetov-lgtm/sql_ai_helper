"""Подсаженные случаи поверх фоновых данных (задача 1.4).

Явные строки для каждой ловушки эталонного запроса №1 (docs/bookstore_text2sql_context.md):
без них неверный SQL может случайно дать тот же ответ, что и верный. Например, если в периоде
нет заказа со скидкой и несколькими позициями, запрос, вычитающий скидку на каждую позицию,
совпадёт с правильным.

Подсаженные строки не пересекаются с фоновыми: свой клиент, свои книги и авторы. Поэтому их
вклад в любой итог — «фон + подсаженные» минус «только фон» — считается вручную по PLANTED_ORDERS.

Периоды (время Asia/Almaty) — на них ссылается тестовый набор (задача 4.1):
- март 2026 — ловушки 1, 2, 3, 6 и возврат февральской продажи (5);
- 31.03.2026 23:50 и 01.04.2026 00:00 — граница месяца (4);
- февраль, март и апрель 2026 — продажа и возврат в разных месяцах (5);
- ноябрь 2024 — месяц с продажами без возвратов (5): правило фона REFUNDS_FROM в generator.py.
"""

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal

from sql_helper.infrastructure.seed.generator import (
    TZ,
    Author,
    Book,
    BookAuthor,
    Dataset,
    Order,
    OrderItem,
    Payment,
    Refund,
    User,
)


def _at(month: int, day: int, hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(2026, month, day, hour, minute, second, tzinfo=TZ)


# ============ Справочные строки подсаженных случаев ============

CUSTOMER = ("Алия", "Нурланова", date(1991, 5, 12), "Алматы", _at(1, 15, 10, 0))

# Ловушка 6: у «Степных хроник» два автора — книга засчитывается каждому из них
# Остальные подсаженные книги — у третьего автора, чтобы не смешивать с ловушкой 6
AUTHORS = [("Ерлан", "Сейткали"), ("Дана", "Абенова"), ("Тимур", "Жумабаев")]
GENRE_ID = 1  # «Художественная литература»

# Ключ → название, цена (она же unit_price во всех заказах), индексы авторов в AUTHORS
BOOKS = {
    "steppe": ("Степные хроники", Decimal("5000.00"), [0, 1]),
    "city": ("Город у гор", Decimal("3000.00"), [2]),
    "notes": ("Заметки на полях", Decimal("2000.00"), [2]),
}


@dataclass(frozen=True)
class PlantedOrder:
    """Заказ подсаженного клиента; все заказы — confirmed."""

    trap: str
    created_at: datetime
    items: list[tuple[str, int]]  # (ключ книги, количество)
    payments: list[tuple[str, datetime, datetime | None]]  # (статус, начало попытки, paid_at)
    promocode: str | None = None
    discount: Decimal = Decimal("0.00")
    refunds: list[tuple[str, int, datetime]] = field(default_factory=list)  # (книга, шт., когда)


# Вклад в выручку месяца по docs/sql-rules.md — в комментарии к каждому заказу
PLANTED_ORDERS = [
    PlantedOrder(
        trap="1. Промокод и несколько позиций: скидка вычитается один раз на заказ",
        created_at=_at(3, 10, 12, 0),
        items=[("city", 2), ("notes", 1)],  # 6 000 + 2 000
        payments=[("succeeded", _at(3, 10, 12, 3), _at(3, 10, 12, 3, 20))],
        promocode="WELCOME",
        discount=Decimal("1000.00"),
        # Ловушка 5: продан в марте, возвращён в апреле — уменьшает апрель, а не март
        refunds=[("notes", 1, _at(4, 5, 16, 30))],
    ),  # март: 8 000 − 1 000 = 7 000; апрель: −2 000
    PlantedOrder(
        trap="2. Неудачный платёж, затем успешный: заказ считается один раз",
        created_at=_at(3, 15, 18, 0),
        items=[("notes", 1)],
        payments=[
            ("failed", _at(3, 15, 18, 2), None),
            ("succeeded", _at(3, 15, 18, 10), _at(3, 15, 18, 10, 15)),
        ],
    ),  # март: 2 000
    PlantedOrder(
        trap="3. confirmed без успешного платежа: в выручку не входит",
        created_at=_at(3, 20, 14, 0),
        items=[("city", 1)],
        payments=[
            ("failed", _at(3, 20, 14, 5), None),
            ("pending", _at(3, 20, 14, 20), None),
        ],
    ),  # 0
    PlantedOrder(
        trap="4. Деньги пришли в 23:50 31 марта — это март",
        created_at=_at(3, 31, 23, 40),
        items=[("notes", 1)],
        payments=[("succeeded", _at(3, 31, 23, 49, 30), _at(3, 31, 23, 50))],
    ),  # март: 2 000
    PlantedOrder(
        trap="4. Деньги пришли ровно в 00:00 1 апреля — это апрель (<, не <=)",
        created_at=_at(3, 31, 23, 55),
        items=[("city", 1)],
        payments=[("succeeded", _at(3, 31, 23, 59, 40), _at(4, 1, 0, 0))],
    ),  # апрель: 3 000
    PlantedOrder(
        trap="5. Продан в феврале, возвращён в марте — уменьшает март",
        created_at=_at(2, 20, 10, 0),
        items=[("notes", 2)],
        payments=[("succeeded", _at(2, 20, 10, 1), _at(2, 20, 10, 1, 30))],
        refunds=[("notes", 1, _at(3, 12, 15, 0))],
    ),  # февраль: 4 000; март: −2 000
    PlantedOrder(
        trap="6. Книга двух авторов: 2 экземпляра засчитываются каждому автору",
        created_at=_at(3, 5, 11, 0),
        items=[("steppe", 2)],
        payments=[("succeeded", _at(3, 5, 11, 2), _at(3, 5, 11, 2, 40))],
    ),  # март: 10 000
]


def add_planted(data: Dataset) -> Dataset:
    """Добавляет подсаженные случаи; id продолжают фоновые (у фона они идут подряд с 1)."""
    name, surname, birthdate, city, registered_at = CUSTOMER
    user = User(len(data.users) + 1, name, surname, birthdate, city, registered_at)

    first_author = len(data.authors) + 1
    authors = [Author(first_author + i, *names) for i, names in enumerate(AUTHORS)]

    first_book = len(data.books) + 1
    books: list[Book] = []
    book_author: list[BookAuthor] = []
    book_ids: dict[str, int] = {}
    for offset, (key, (title, price, author_indexes)) in enumerate(BOOKS.items()):
        book_ids[key] = first_book + offset
        books.append(Book(book_ids[key], title, price, None, GENRE_ID))
        book_author.extend(BookAuthor(book_ids[key], authors[i].id) for i in author_indexes)

    promocode_ids = {code.name: code.id for code in data.promocodes}
    orders: list[Order] = []
    items: list[OrderItem] = []
    payments: list[Payment] = []
    refunds: list[Refund] = []
    order_id = len(data.orders) + 1
    item_id = len(data.order_item) + 1
    payment_id = len(data.payments) + 1
    refund_id = len(data.refunds) + 1

    for planted in PLANTED_ORDERS:
        promocode_id = promocode_ids[planted.promocode] if planted.promocode else None
        orders.append(
            Order(
                order_id,
                user.id,
                planted.created_at,
                "confirmed",
                promocode_id,
                planted.discount,
            )
        )
        item_by_book: dict[str, int] = {}
        for key, quantity in planted.items:
            price = BOOKS[key][1]
            items.append(OrderItem(item_id, order_id, book_ids[key], price, quantity))
            item_by_book[key] = item_id
            item_id += 1
        for status, started_at, paid_at in planted.payments:
            payments.append(Payment(payment_id, order_id, status, started_at, paid_at))
            payment_id += 1
        for key, quantity, refunded_at in planted.refunds:
            refunds.append(Refund(refund_id, item_by_book[key], quantity, None, refunded_at))
            refund_id += 1
        order_id += 1

    return replace(
        data,
        authors=[*data.authors, *authors],
        users=[*data.users, user],
        books=[*data.books, *books],
        book_author=[*data.book_author, *book_author],
        orders=[*data.orders, *orders],
        order_item=[*data.order_item, *items],
        payments=[*data.payments, *payments],
        refunds=[*data.refunds, *refunds],
    )
