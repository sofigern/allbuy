import importlib.util
import pathlib
from dataclasses import asdict, fields, MISSING

import flatdict
import pytest

# The entrypoint is ``__main__.py``; under pytest that name is already taken,
# so it is loaded by path.
_spec = importlib.util.spec_from_file_location(
    "allbuy_main", pathlib.Path(__file__).resolve().parent.parent / "__main__.py"
)
_entrypoint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_entrypoint)
write_orders = _entrypoint.write_orders
from src.models.client import Client
from src.models.order import Order
from src.models.order_product import OrderProduct


class FakeSheet:
    def __init__(self):
        self.cleared = False
        self.rows = []
        self.header = None

    def clear(self):
        self.cleared = True

    def append_row(self, row):
        self.header = row

    def append_rows(self, rows):
        self.rows.extend(rows)


class FakeClient:
    def __init__(self, sheet):
        self._sheet = sheet

    def open(self, _title):
        return self

    def worksheet(self, _name):
        return self._sheet


def make_order(**overrides):
    values = {
        f.name: None
        for f in fields(Order)
        if f.default is MISSING and f.default_factory is MISSING
    }
    values.update(id=1, delivery_address="Харків", client=Client())
    values.update(overrides)
    return flatdict.FlatDict(asdict(Order(**values)), delimiter=".")


@pytest.fixture
def sheet():
    return FakeSheet()


def test_omits_the_column_of_a_composite_field(sheet):
    orders = {
        "1": make_order(products=[OrderProduct(sku="HT-0103", quantity=2.0)])
    }

    write_orders(FakeClient(sheet), "Paid", orders)

    assert "products" not in sheet.header


def test_writes_the_scalar_columns_of_an_order_with_products(sheet):
    orders = {
        "1": make_order(
            delivery_address="Харків",
            products=[OrderProduct(sku="HT-0103", quantity=2.0)],
        )
    }

    write_orders(FakeClient(sheet), "Paid", orders)

    row = dict(zip(sheet.header, sheet.rows[0]))
    assert row["id"] == 1
    assert row["delivery_address"] == "Харків"


def test_every_written_cell_holds_a_single_value(sheet):
    orders = {
        "1": make_order(products=[OrderProduct(sku="HT-0103", quantity=2.0)]),
        "2": make_order(id=2, products=[]),
    }

    write_orders(FakeClient(sheet), "Paid", orders)

    for row in sheet.rows:
        for value in row:
            assert value is None or isinstance(value, (str, int, float, bool))


def test_blanks_a_branch_an_order_left_empty_elsewhere(sheet):
    """One order's empty field names a column that is a branch in another.

    ``flatdict`` reports ``payment_data`` as a leaf where it is ``None`` and as
    ``payment_data.type`` where it is filled, so both become columns.
    """
    orders = {
        "1": flatdict.FlatDict({"id": 1, "payment_data": {"type": "card"}}, delimiter="."),
        "2": flatdict.FlatDict({"id": 2, "payment_data": None}, delimiter="."),
    }

    write_orders(FakeClient(sheet), "Pending", orders)

    for row in sheet.rows:
        for value in row:
            assert value is None or isinstance(value, (str, int, float, bool))
