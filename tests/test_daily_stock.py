import datetime

import pytest

from daily_stock import (
    IN_STOCK,
    NOT_ENOUGH,
    UNKNOWN,
    build_report,
    orders_in_window,
    render_email,
)
from src.clock import KYIV, daily_window, to_kyiv
from src.models.order_product import OrderProduct
from src.models.product import Product


class FakeStatus:
    def __init__(self, name):
        self.name = name


class FakeOrder:
    def __init__(self, id, created, lines, status="delivered"):
        self.id = id
        self.date_created = created
        self.products = lines
        self.status = FakeStatus(status)

    @property
    def datetime_created(self):
        return to_kyiv(self.date_created)


def line(sku, quantity, name=None):
    return OrderProduct(sku=sku, quantity=quantity, name=name or f"товар {sku}")


def stock(sku, quantity):
    return Product(sku=sku, name=f"stock {sku}", quantity_in_stock=quantity)


def kyiv(value):
    return datetime.datetime.fromisoformat(value).replace(tzinfo=KYIV)


# --- the window ------------------------------------------------------------

@pytest.mark.parametrize(
    "now, expected_start, expected_end",
    [
        # Run at 08:50 exactly: yesterday 08:50 -> today 08:50.
        ("2026-09-11T08:50:00", "2026-09-10T08:50:00", "2026-09-11T08:50:00"),
        # A minute early still belongs to the previous window.
        ("2026-09-11T08:49:59", "2026-09-09T08:50:00", "2026-09-10T08:50:00"),
        # A late run reports the same window as the on-time one.
        ("2026-09-11T23:10:00", "2026-09-10T08:50:00", "2026-09-11T08:50:00"),
    ],
)
def test_daily_window(now, expected_start, expected_end):
    start, end = daily_window(kyiv(now))
    assert (start, end) == (kyiv(expected_start), kyiv(expected_end))


def test_utc_and_naive_timestamps_are_the_same_instant():
    # The bug this guards: Prom sends an offset, the cabinet sends naive
    # Kyiv, and stripping the offset silently shifted the window by it.
    assert to_kyiv("2026-09-11T05:50:00+00:00") == to_kyiv("2026-09-11T08:50:00")


def test_window_boundary_is_half_open():
    start, end = daily_window(kyiv("2026-09-11T08:50:00"))
    orders = [
        FakeOrder(1, "2026-09-10T08:49:59+03:00", []),   # before
        FakeOrder(2, "2026-09-10T08:50:00+03:00", []),   # first instant in
        FakeOrder(3, "2026-09-11T08:49:59+03:00", []),   # last instant in
        FakeOrder(4, "2026-09-11T08:50:00+03:00", []),   # next window
    ]
    assert [o.id for o in orders_in_window(orders, start, end)] == [2, 3]


def test_utc_offset_order_lands_in_the_right_window():
    # 2026-09-10T05:50:00+00:00 is exactly 08:50 Kyiv, the first instant
    # of the window. Read as naive it would fall a day earlier and vanish.
    start, end = daily_window(kyiv("2026-09-11T08:50:00"))
    order = FakeOrder(1, "2026-09-10T05:50:00+00:00", [])
    assert orders_in_window([order], start, end) == [order]


# --- the report ------------------------------------------------------------

def test_quantities_sum_across_orders_and_lines():
    rows = build_report(
        orders=[
            FakeOrder(1, "2026-09-10T10:00:00+03:00", [line("HT-6001", 2)]),
            FakeOrder(2, "2026-09-10T11:00:00+03:00", [line("HT-6001", 3)]),
        ],
        stock_products=[stock("HT-6001", 10)],
    )
    [row] = rows
    assert (row.ordered, row.orders, row.in_stock, row.status) == (5, 2, 10, IN_STOCK)


def test_every_position_appears_even_when_fully_in_stock():
    # The report is not filtered to shortfalls; a stocked line still shows.
    rows = build_report(
        orders=[FakeOrder(1, "2026-09-10T10:00:00+03:00", [line("HT-6001", 1)])],
        stock_products=[stock("HT-6001", 99)],
    )
    assert [r.sku for r in rows] == ["HT-6001"]
    assert rows[0].status == IN_STOCK


def test_shortfall_and_missing_sku_are_distinct_states():
    rows = build_report(
        orders=[
            FakeOrder(1, "2026-09-10T10:00:00+03:00", [line("SHORT-1", 5)]),
            FakeOrder(2, "2026-09-10T10:00:00+03:00", [line("ABSENT-1", 1)]),
        ],
        stock_products=[stock("SHORT-1", 2)],
    )
    by_sku = {row.sku: row for row in rows}
    assert by_sku["SHORT-1"].status == NOT_ENOUGH
    assert by_sku["SHORT-1"].in_stock == 2
    assert by_sku["ABSENT-1"].status == UNKNOWN
    assert by_sku["ABSENT-1"].in_stock is None
    assert by_sku["ABSENT-1"].as_row()[3] == "—"


def test_zero_stock_is_not_treated_as_missing():
    [row] = build_report(
        orders=[FakeOrder(1, "2026-09-10T10:00:00+03:00", [line("ZERO-1", 1)])],
        stock_products=[stock("ZERO-1", 0)],
    )
    assert (row.in_stock, row.status) == (0, NOT_ENOUGH)


def test_sheet_skus_with_stray_whitespace_still_match():
    # The TC-7635 case: the sheet is hand-edited and carries newlines.
    [row] = build_report(
        orders=[FakeOrder(1, "2026-09-10T10:00:00+03:00", [line("TC-7635", 1)])],
        stock_products=[stock("TC-7635\n\n", 35)],
    )
    assert (row.in_stock, row.status) == (35, IN_STOCK)


def test_shortfalls_sort_above_stocked_lines():
    rows = build_report(
        orders=[
            FakeOrder(1, "2026-09-10T10:00:00+03:00", [
                line("OK-1", 100), line("SHORT-1", 1), line("ABSENT-1", 1),
            ]),
        ],
        stock_products=[stock("OK-1", 999), stock("SHORT-1", 0)],
    )
    assert [row.sku for row in rows] == ["SHORT-1", "ABSENT-1", "OK-1"]


def test_lines_without_sku_are_skipped():
    rows = build_report(
        orders=[FakeOrder(1, "2026-09-10T10:00:00+03:00", [
            OrderProduct(sku=None, quantity=1, name="без артикула"),
        ])],
        stock_products=[],
    )
    assert rows == []


# --- the email -------------------------------------------------------------

def test_email_reports_counts_and_lists_every_row():
    start, end = daily_window(kyiv("2026-09-11T08:50:00"))
    rows = build_report(
        orders=[FakeOrder(1, "2026-09-10T10:00:00+03:00", [
            line("SHORT-1", 5), line("OK-1", 1),
        ])],
        stock_products=[stock("SHORT-1", 1), stock("OK-1", 9)],
    )
    subject, body = render_email(rows, start, end)

    assert "11.09.2026" in subject
    assert "2 позицій" in subject and "1 під питанням" in subject
    assert "SHORT-1" in body and "OK-1" in body
    assert "10.09.2026 08:50 — 11.09.2026 08:50" in body


def test_empty_day_says_so_rather_than_rendering_a_bare_header():
    start, end = daily_window(kyiv("2026-09-11T08:50:00"))
    subject, body = render_email([], start, end)
    assert "0 позицій" in subject
    assert "За цей період замовлень не було." in body


def test_float_quantities_do_not_render_as_decimals():
    # Prom types quantity as a float; 1.0 units should read as "1".
    [row] = build_report(
        orders=[FakeOrder(1, "2026-09-10T10:00:00+03:00", [line("HT-6001", 2.0)])],
        stock_products=[stock("HT-6001", 5)],
    )
    assert row.as_row()[2] == "2"


def test_long_product_names_are_trimmed_only_for_the_mail():
    long_name = "Професійний набір інструментів " * 5
    [row] = build_report(
        orders=[FakeOrder(1, "2026-09-10T10:00:00+03:00", [
            line("ET-7176", 1, name=long_name),
        ])],
        stock_products=[stock("ET-7176", 1)],
    )
    assert row.as_row()[1] == long_name          # worksheet keeps it whole
    assert len(row.as_row(58)[1]) == 58          # the mail column does not
    assert row.as_row(58)[1].endswith("…")
