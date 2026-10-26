"""Фоновые данные магазина: Faker + random с фиксированным seed (задача 1.3).

Генерация — чистая функция без базы: одинаковый seed даёт одинаковые строки.
Запись в базу — loader.py. Все случайные решения берутся из одного random.Random и одного
Faker, вызываемых в фиксированном порядке; функции Faker, зависящие от текущей даты
(например, date_of_birth), не используются — иначе данные менялись бы день ото дня.
"""

import bisect
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import NamedTuple
from zoneinfo import ZoneInfo

from faker import Faker

TZ = ZoneInfo("Asia/Almaty")
PERIOD_START = datetime(2024, 11, 1, tzinfo=TZ)
PERIOD_END = datetime(2026, 11, 1, tzinfo=TZ)  # не включительно

DEFAULT_SEED = 42
N_USERS = 2_000
N_BOOKS = 300
N_AUTHORS = 180
N_ORDERS = 10_000


# ============ Строки таблиц: имена полей = имена колонок shop ============


class Genre(NamedTuple):
    id: int
    name: str


class Author(NamedTuple):
    id: int
    name: str
    surname: str


class User(NamedTuple):
    id: int
    name: str
    surname: str
    birthdate: date | None
    city: str | None
    registered_at: datetime


class Promocode(NamedTuple):
    id: int
    name: str
    discount_sum: Decimal


class Book(NamedTuple):
    id: int
    title: str
    price: Decimal
    pages: int | None
    genre_id: int


class BookAuthor(NamedTuple):
    book_id: int
    author_id: int


class Order(NamedTuple):
    id: int
    user_id: int
    created_at: datetime
    status: str
    promocode_id: int | None
    discount_per_order: Decimal


class OrderItem(NamedTuple):
    id: int
    order_id: int
    book_id: int
    unit_price: Decimal
    quantity: int


class Payment(NamedTuple):
    id: int
    order_id: int
    status: str
    created_at: datetime
    paid_at: datetime | None


class Refund(NamedTuple):
    id: int
    order_item_id: int
    quantity: int
    reason: str | None
    refunded_at: datetime


@dataclass(frozen=True)
class Dataset:
    genres: list[Genre]
    authors: list[Author]
    users: list[User]
    promocodes: list[Promocode]
    books: list[Book]
    book_author: list[BookAuthor]
    orders: list[Order]
    order_item: list[OrderItem]
    payments: list[Payment]
    refunds: list[Refund]


# ============ Параметры закономерностей ============

GENRES = [
    ("Художественная литература", 18),
    ("Детективы", 10),
    ("Фантастика", 8),
    ("Фэнтези", 8),
    ("Детская литература", 10),
    ("Учебная литература", 9),
    ("Бизнес", 6),
    ("Психология", 6),
    ("История", 5),
    ("Научно-популярное", 6),
    ("Поэзия", 3),
    ("Комиксы и манга", 4),
    ("Саморазвитие", 5),
    ("Кулинария", 2),
]

CITIES = [
    ("Алматы", 30),
    ("Астана", 22),
    ("Шымкент", 10),
    ("Караганда", 7),
    ("Актобе", 5),
    ("Усть-Каменогорск", 4),
    ("Павлодар", 4),
    ("Атырау", 4),
    ("Костанай", 3),
    ("Тараз", 3),
    ("Уральск", 3),
    ("Семей", 3),
    ("Кызылорда", 2),
]
NO_CITY_SHARE = 0.12
NO_BIRTHDATE_SHARE = 0.15

# Сентябрь — к учебному году, декабрь — подарки; январь и лето — спад
MONTH_WEIGHTS = {
    1: 0.80,
    2: 0.85,
    3: 0.95,
    4: 0.95,
    5: 0.90,
    6: 0.80,
    7: 0.75,
    8: 1.00,
    9: 1.60,
    10: 1.05,
    11: 1.10,
    12: 1.80,
}
MONTHLY_GROWTH = 0.015  # магазин понемногу растёт: +1.5% заказов за месяц

# Покупают днём и вечером, ночью почти нет
HOUR_WEIGHTS = [1, 1, 1, 1, 1, 1, 2, 4, 6, 8, 9, 10, 11, 11, 10, 10, 10, 11, 13, 14, 13, 10, 6, 3]

ITEMS_PER_ORDER = [(1, 55), (2, 28), (3, 12), (4, 5)]
QUANTITY = [(1, 82), (2, 13), (3, 5)]

# Хиты: популярность книги ~ 1 / ранг (закон Ципфа) — топ-20% книг дают ~3/4 экземпляров
ZIPF_EXPONENT = 1.0
TWO_AUTHORS_SHARE = 0.08

PRICE_INFLATION_PER_YEAR = 0.08  # unit_price в старых заказах ниже текущей books.price

PROMOCODES = [
    ("WELCOME", 1000),
    ("AUTUMN", 1500),
    ("SCHOOL", 2000),
    ("NEWYEAR", 2500),
    ("SPRING", 1200),
    ("READER", 800),
    ("BOOKCLUB", 1800),
    ("FRIDAY", 700),
    ("SUMMER", 1000),
    ("VIP", 3000),
]
PROMOCODE_SHARE = 0.15
PROMOCODE_CHANGED_SHARE = 0.5  # у половины промокодов скидка менялась: старые заказы — по старой

CANCELLED_SHARE = 0.07
PENDING_SHARE = 0.015
PENDING_SHARE_LAST_DAYS = 0.40  # заказы последних дней периода ещё не обработаны
LAST_DAYS = timedelta(days=10)

FAILED_ATTEMPTS = [(0, 85), (1, 12), (2, 3)]  # неудачные попытки перед успешной
PAID_NEXT_DAY_SHARE = 0.05
# Принят, но не оплачен: оплата идёт или не прошла — в выручку не входит (docs/sql-rules.md)
CONFIRMED_UNPAID_SHARE = 0.02

REFUND_ITEM_SHARE = 0.035
SECOND_REFUND_SHARE = 0.2  # вторая частичная доля возврата той же позиции
# Первый месяц магазин возвратов не принимал: месяц с продажами без возвратов нужен
# для ловушки «SUM по пустому набору = NULL» (planted.py, случай 5)
REFUNDS_FROM = datetime(2024, 12, 1, tzinfo=TZ)
REFUND_REASONS = [
    ("Брак печати", 25),
    ("Повреждена при доставке", 20),
    ("Не подошла", 25),
    ("Передумал", 15),
    (None, 15),
]

ACTIVITY_PARETO_ALPHA = 1.3  # немногие клиенты покупают часто — повторные покупатели
ACTIVITY_CAP = 15.0  # без потолка хвост Парето даёт клиента с сотнями заказов
LAUNCH_USERS_SHARE = 0.15  # пришли в первый месяц работы магазина

CENT = Decimal("0.01")


# ============ Вспомогательное ============


class _WeightedPicker:
    """Выбор по весам за O(log n): накопленные суммы + бинарный поиск."""

    def __init__(self, weights: list[float]) -> None:
        self._cumulative: list[float] = []
        total = 0.0
        for weight in weights:
            total += weight
            self._cumulative.append(total)

    def pick(self, rng: random.Random, upto: int | None = None) -> int:
        """Индекс по весам среди первых upto элементов (все, если upto не задан)."""
        limit = len(self._cumulative) if upto is None else upto
        point = rng.random() * self._cumulative[limit - 1]
        return min(bisect.bisect_right(self._cumulative, point), limit - 1)


def _choice[T](rng: random.Random, options: list[tuple[T, int]]) -> T:
    values = [value for value, _ in options]
    weights = [weight for _, weight in options]
    return rng.choices(values, weights=weights)[0]


def _random_moment(rng: random.Random, start: datetime, end: datetime) -> datetime:
    seconds = int((end - start).total_seconds())
    return start + timedelta(seconds=rng.randrange(seconds))


def _month_starts() -> list[datetime]:
    starts = []
    current = PERIOD_START
    while current < PERIOD_END:
        starts.append(current)
        year, month = (
            (current.year + 1, 1) if current.month == 12 else (current.year, current.month + 1)
        )
        current = current.replace(year=year, month=month)
    return starts


def _orders_per_month(month_starts: list[datetime]) -> list[int]:
    """Делит N_ORDERS по месяцам пропорционально весам (метод наибольших остатков)."""
    weights = [
        MONTH_WEIGHTS[start.month] * (1 + MONTHLY_GROWTH * index)
        for index, start in enumerate(month_starts)
    ]
    total = sum(weights)
    exact = [N_ORDERS * weight / total for weight in weights]
    counts = [int(value) for value in exact]
    by_remainder = sorted(range(len(exact)), key=lambda i: exact[i] - counts[i], reverse=True)
    for index in by_remainder[: N_ORDERS - sum(counts)]:
        counts[index] += 1
    return counts


def _order_moment(rng: random.Random, month_start: datetime, month_end: datetime) -> datetime:
    days = (month_end.date() - month_start.date()).days
    day = month_start + timedelta(days=rng.randrange(days))
    hour = rng.choices(range(24), weights=HOUR_WEIGHTS)[0]
    return day + timedelta(hours=hour, minutes=rng.randrange(60), seconds=rng.randrange(60))


def _historical_price(current: Decimal, moment: datetime) -> Decimal:
    years_before_end = (PERIOD_END - moment).days / 365
    factor = Decimal(str(round((1 + PRICE_INFLATION_PER_YEAR) ** -years_before_end, 4)))
    return (current * factor / 10).quantize(Decimal("1")) * 10  # цены кратны 10 ₸


# ============ Генерация ============


def generate(seed: int = DEFAULT_SEED) -> Dataset:
    rng = random.Random(seed)
    fake = Faker("ru_RU")
    fake.seed_instance(seed)

    genres = [Genre(i, name) for i, (name, _) in enumerate(GENRES, start=1)]
    authors = [_author(fake, rng, i) for i in range(1, N_AUTHORS + 1)]
    users = _users(fake, rng)
    promocodes, discount_history = _promocodes(rng)
    books, book_author, book_picker = _books(fake, rng, genres, authors)
    orders, items, payments, refunds = _orders(rng, users, books, book_picker, discount_history)

    return Dataset(
        genres=genres,
        authors=authors,
        users=users,
        promocodes=promocodes,
        books=books,
        book_author=book_author,
        orders=orders,
        order_item=items,
        payments=payments,
        refunds=refunds,
    )


def _person_name(fake: Faker, rng: random.Random) -> tuple[str, str]:
    if rng.random() < 0.5:
        return fake.first_name_male(), fake.last_name_male()
    return fake.first_name_female(), fake.last_name_female()


def _author(fake: Faker, rng: random.Random, author_id: int) -> Author:
    name, surname = _person_name(fake, rng)
    return Author(author_id, name, surname)


def _users(fake: Faker, rng: random.Random) -> list[User]:
    launch_end = PERIOD_START + timedelta(days=30)
    moments = sorted(
        _random_moment(
            rng, PERIOD_START, launch_end if rng.random() < LAUNCH_USERS_SHARE else PERIOD_END
        )
        for _ in range(N_USERS)
    )
    cities = [city for city, _ in CITIES]
    city_weights = [weight for _, weight in CITIES]
    users = []
    for user_id, registered_at in enumerate(moments, start=1):
        name, surname = _person_name(fake, rng)
        birthdate = None
        if rng.random() >= NO_BIRTHDATE_SHARE:
            birthdate = date(1955, 1, 1) + timedelta(days=rng.randrange(365 * 54))
        city = None
        if rng.random() >= NO_CITY_SHARE:
            city = rng.choices(cities, weights=city_weights)[0]
        users.append(User(user_id, name, surname, birthdate, city, registered_at))
    return users


@dataclass(frozen=True)
class _DiscountHistory:
    """Скидка промокода во времени: до changed_at действовала previous, после — current."""

    current: Decimal
    previous: Decimal
    changed_at: datetime | None

    def at(self, moment: datetime) -> Decimal:
        if self.changed_at is not None and moment < self.changed_at:
            return self.previous
        return self.current


def _promocodes(rng: random.Random) -> tuple[list[Promocode], dict[int, _DiscountHistory]]:
    codes = []
    history = {}
    for code_id, (name, amount) in enumerate(PROMOCODES, start=1):
        current = Decimal(amount).quantize(CENT)
        changed_at = None
        previous = current
        if rng.random() < PROMOCODE_CHANGED_SHARE:
            changed_at = _random_moment(rng, PERIOD_START + timedelta(days=90), PERIOD_END)
            previous = (current - Decimal(rng.choice([200, 300, 500]))).quantize(CENT)
        codes.append(Promocode(code_id, name, current))
        history[code_id] = _DiscountHistory(current, previous, changed_at)
    return codes, history


def _book_title(fake: Faker, rng: random.Random) -> str:
    words = fake.words(nb=rng.choices([1, 2, 3, 4], weights=[15, 40, 30, 15])[0])
    return " ".join(words).capitalize()


def _books(
    fake: Faker, rng: random.Random, genres: list[Genre], authors: list[Author]
) -> tuple[list[Book], list[BookAuthor], _WeightedPicker]:
    genre_weights = [weight for _, weight in GENRES]
    books = []
    book_author = []
    for book_id in range(1, N_BOOKS + 1):
        genre = rng.choices(genres, weights=genre_weights)[0]
        price = Decimal(rng.randrange(1500, 12001, 100)).quantize(CENT)
        pages = None if rng.random() < 0.03 else rng.randrange(60, 900)
        books.append(Book(book_id, _book_title(fake, rng), price, pages, genre.id))
        n_authors = 2 if rng.random() < TWO_AUTHORS_SHARE else 1
        for author in rng.sample(authors, n_authors):
            book_author.append(BookAuthor(book_id, author.id))

    # Ранги популярности перемешаны, чтобы хиты не совпадали с первыми id
    ranks = list(range(1, N_BOOKS + 1))
    rng.shuffle(ranks)
    picker = _WeightedPicker([1 / rank**ZIPF_EXPONENT for rank in ranks])
    return books, book_author, picker


def _orders(
    rng: random.Random,
    users: list[User],
    books: list[Book],
    book_picker: _WeightedPicker,
    discount_history: dict[int, _DiscountHistory],
) -> tuple[list[Order], list[OrderItem], list[Payment], list[Refund]]:
    # Пользователи отсортированы по registered_at: покупать могут только уже зарегистрированные
    registered = [user.registered_at for user in users]
    user_picker = _WeightedPicker(
        [min(rng.paretovariate(ACTIVITY_PARETO_ALPHA), ACTIVITY_CAP) for _ in users]
    )

    orders: list[Order] = []
    items: list[OrderItem] = []
    payments: list[Payment] = []
    refunds: list[Refund] = []

    month_starts = _month_starts()
    month_ends = [*month_starts[1:], PERIOD_END]
    moments: list[datetime] = []
    for start, end, count in zip(
        month_starts, month_ends, _orders_per_month(month_starts), strict=True
    ):
        moments.extend(_order_moment(rng, start, end) for _ in range(count))
    moments.sort()

    for order_id, created_at in enumerate(moments, start=1):
        eligible = max(bisect.bisect_right(registered, created_at), 1)
        user = users[user_picker.pick(rng, upto=eligible)]
        created_at = max(created_at, user.registered_at + timedelta(minutes=rng.randrange(5, 60)))
        created_at = min(created_at, PERIOD_END - timedelta(seconds=1))

        order_items = _order_items(rng, len(items) + 1, order_id, created_at, books, book_picker)
        items.extend(order_items)
        subtotal = sum((item.unit_price * item.quantity for item in order_items), Decimal(0))

        promocode_id = None
        discount = Decimal(0).quantize(CENT)
        if rng.random() < PROMOCODE_SHARE:
            promocode_id = rng.randrange(1, len(discount_history) + 1)
            # Правило приложения: скидка не больше суммы заказа
            discount = min(discount_history[promocode_id].at(created_at), subtotal)

        status = _order_status(rng, created_at)
        orders.append(Order(order_id, user.id, created_at, status, promocode_id, discount))

        paid_at = _payments(rng, payments, order_id, status, created_at)
        if paid_at is not None and status == "confirmed":
            _refunds(rng, refunds, order_items, paid_at)

    return orders, items, payments, refunds


def _order_items(
    rng: random.Random,
    first_id: int,
    order_id: int,
    created_at: datetime,
    books: list[Book],
    book_picker: _WeightedPicker,
) -> list[OrderItem]:
    count = _choice(rng, ITEMS_PER_ORDER)
    chosen: list[int] = []
    while len(chosen) < count:  # одна книга = одна позиция
        index = book_picker.pick(rng)
        if index not in chosen:
            chosen.append(index)
    return [
        OrderItem(
            first_id + offset,
            order_id,
            books[index].id,
            _historical_price(books[index].price, created_at),
            _choice(rng, QUANTITY),
        )
        for offset, index in enumerate(chosen)
    ]


def _order_status(rng: random.Random, created_at: datetime) -> str:
    roll = rng.random()
    if roll < CANCELLED_SHARE:
        return "cancelled"
    pending_share = (
        PENDING_SHARE_LAST_DAYS if created_at >= PERIOD_END - LAST_DAYS else PENDING_SHARE
    )
    if roll < CANCELLED_SHARE + pending_share:
        return "pending"
    return "confirmed"


def _payments(
    rng: random.Random, payments: list[Payment], order_id: int, status: str, created_at: datetime
) -> datetime | None:
    """Добавляет платежи заказа; возвращает paid_at успешного платежа, если он есть."""

    def add(payment_status: str, at: datetime, paid_at: datetime | None = None) -> None:
        payments.append(Payment(len(payments) + 1, order_id, payment_status, at, paid_at))

    cursor = created_at + timedelta(minutes=rng.randrange(1, 30))
    if status == "confirmed":
        for _ in range(_choice(rng, FAILED_ATTEMPTS)):
            add("failed", cursor)
            cursor += timedelta(minutes=rng.randrange(2, 60))
        if rng.random() < CONFIRMED_UNPAID_SHARE:
            add(rng.choice(["pending", "failed"]), cursor)
            return None
        if rng.random() < PAID_NEXT_DAY_SHARE:
            cursor += timedelta(days=1)
        paid_at = cursor + timedelta(seconds=rng.randrange(5, 120))
        if paid_at >= PERIOD_END:  # деньги придут уже после периода данных
            add("pending", cursor)
            return None
        add("succeeded", cursor, paid_at)
        return paid_at

    roll = rng.random()
    if status == "cancelled":
        # Отменить можно только до оплаты (docs/sql-rules.md): успешного платежа нет
        if roll < 0.30:
            add("failed", cursor)
        return None

    # pending: заказ ещё не обработан
    if roll < 0.35:
        add("pending", cursor)
    elif roll < 0.50:
        add("failed", cursor)
    return None


def _refunds(
    rng: random.Random, refunds: list[Refund], order_items: list[OrderItem], paid_at: datetime
) -> None:
    for item in order_items:
        if rng.random() >= REFUND_ITEM_SHARE:
            continue
        # Правило приложения: вернуть можно не больше, чем куплено
        remaining = item.quantity
        moment = max(paid_at, REFUNDS_FROM)
        while remaining > 0:
            quantity = rng.randint(1, remaining)
            moment += timedelta(days=rng.randrange(1, 30), seconds=rng.randrange(86_400))
            if moment >= PERIOD_END:
                break
            reason = _choice(rng, REFUND_REASONS)
            refunds.append(Refund(len(refunds) + 1, item.id, quantity, reason, moment))
            remaining -= quantity
            if rng.random() >= SECOND_REFUND_SHARE:
                break
