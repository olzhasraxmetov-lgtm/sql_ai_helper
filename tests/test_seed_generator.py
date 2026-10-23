"""Генератор фоновых данных без базы: детерминизм и правила уровня приложения."""

from collections import defaultdict
from decimal import Decimal

import pytest

from sql_helper.infrastructure.seed.generator import PERIOD_END, PERIOD_START, Dataset, generate


@pytest.fixture(scope="module")
def data() -> Dataset:
    return generate(seed=42)


def test_same_seed_gives_same_data(data: Dataset) -> None:
    assert generate(seed=42) == data


def test_other_seed_gives_other_data(data: Dataset) -> None:
    assert generate(seed=7).orders != data.orders


def test_discount_not_greater_than_order_sum(data: Dataset) -> None:
    subtotal: dict[int, Decimal] = defaultdict(Decimal)
    for item in data.order_item:
        subtotal[item.order_id] += item.unit_price * item.quantity

    too_big = [o.id for o in data.orders if o.discount_per_order > subtotal[o.id]]

    assert too_big == []


def test_refunded_not_more_than_bought(data: Dataset) -> None:
    refunded: dict[int, int] = defaultdict(int)
    for refund in data.refunds:
        refunded[refund.order_item_id] += refund.quantity
    bought = {item.id: item.quantity for item in data.order_item}

    too_many = [item_id for item_id, qty in refunded.items() if qty > bought[item_id]]

    assert too_many == []


def test_succeeded_payment_only_for_confirmed_orders(data: Dataset) -> None:
    status = {order.id: order.status for order in data.orders}

    paid_not_confirmed = [
        p.order_id
        for p in data.payments
        if p.status == "succeeded" and status[p.order_id] != "confirmed"
    ]

    assert paid_not_confirmed == []


def test_some_confirmed_orders_are_not_paid(data: Dataset) -> None:
    # Нужно для ловушки «фильтр только по статусу»: confirmed без succeeded не входит в выручку
    paid = {p.order_id for p in data.payments if p.status == "succeeded"}

    unpaid_confirmed = [o.id for o in data.orders if o.status == "confirmed" and o.id not in paid]

    assert unpaid_confirmed


def test_refunds_only_for_paid_confirmed_orders(data: Dataset) -> None:
    confirmed = {order.id for order in data.orders if order.status == "confirmed"}
    paid = {p.order_id for p in data.payments if p.status == "succeeded"}
    item_order = {item.id: item.order_id for item in data.order_item}

    refunded_orders = {item_order[refund.order_item_id] for refund in data.refunds}

    assert refunded_orders <= confirmed & paid


def test_events_are_inside_period_and_in_order(data: Dataset) -> None:
    orders = {order.id: order for order in data.orders}
    users = {user.id: user for user in data.users}
    paid_at = {p.order_id: p.paid_at for p in data.payments if p.paid_at is not None}
    item_order = {item.id: item.order_id for item in data.order_item}

    for order in data.orders:
        assert PERIOD_START <= order.created_at < PERIOD_END
        assert users[order.user_id].registered_at <= order.created_at
    for payment in data.payments:
        assert orders[payment.order_id].created_at <= payment.created_at
        assert payment.paid_at is None or payment.paid_at < PERIOD_END
    for refund in data.refunds:
        assert paid_at[item_order[refund.order_item_id]] < refund.refunded_at < PERIOD_END
