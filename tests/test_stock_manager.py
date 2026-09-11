import gspread
import pytest

from src.stock.stock_manager import StockManager

HEADER = ["Артикул", "Товар", "Кількість", "Од.", "МРРЦ", "Базова", "Ціна", "Сума"]


class FakeWorksheet:
    def __init__(self, title):
        self.title = title
        self.rows: list[list] = []

    def append_row(self, row):
        self.rows.append(list(row))

    def append_rows(self, rows):
        self.rows.extend(list(row) for row in rows)

    def clear(self):
        self.rows = []


class FakeSpreadsheet:
    """Just enough of gspread's Spreadsheet to exercise write_report."""

    def __init__(self, worksheets=()):
        self._worksheets = {ws.title: ws for ws in worksheets}

    def worksheets(self):
        return list(self._worksheets.values())

    def worksheet(self, title):
        try:
            return self._worksheets[title]
        except KeyError:
            raise gspread.exceptions.WorksheetNotFound(title) from None

    def add_worksheet(self, title, rows, cols, index=1):
        # The real Sheets API refuses a duplicate title outright.
        if title in self._worksheets:
            raise gspread.exceptions.GSpreadException(f"duplicate title {title!r}")
        worksheet = FakeWorksheet(title)
        self._worksheets[title] = worksheet
        return worksheet


class FakeClient:
    def __init__(self, spreadsheet):
        self._spreadsheet = spreadsheet

    def open(self, name):
        return self._spreadsheet


def make_manager(worksheets=()):
    """A StockManager over a FakeSpreadsheet, with a "Товари" tab so
    __init__'s own worksheet lookup succeeds."""
    spreadsheet = FakeSpreadsheet([FakeWorksheet("Товари"), *worksheets])
    return StockManager(
        client=FakeClient(spreadsheet), spreadsheet="Склад Intertool", worksheet="Товари"
    )


def test_parse_rows_strips_stray_whitespace_from_sku_and_name():
    data = [
        HEADER,
        [
            "TC-7635\n\n", "Хомут пластиковий\n\n", "35", "шт",
            "145,00", "159,00", "115,20", "4032,00",
        ],
    ]
    [product] = StockManager.parse_rows(data)
    assert product.sku == "TC-7635"
    assert product.name == "Хомут пластиковий"
    assert product.quantity_in_stock == 35
    assert product.price == 115.20


def test_parse_rows_selects_columns_by_header_name_not_position():
    data = [
        ["Товар", "Артикул", "Ціна", "Кількість"],
        ["Лубрикатор", "PT-1421", "199,00", "22"],
    ]
    [product] = StockManager.parse_rows(data)
    assert product.sku == "PT-1421"
    assert product.name == "Лубрикатор"
    assert product.quantity_in_stock == 22
    assert product.price == 199.0


def test_parse_rows_treats_empty_quantity_as_zero_and_skips_blank_sku_rows():
    data = [
        HEADER,
        ["PT-1421", "Лубрикатор", "", "шт", "", "", "199,00", ""],
        ["", "", "", "", "", "", "", ""],
    ]
    [product] = StockManager.parse_rows(data)
    assert product.sku == "PT-1421"
    assert product.quantity_in_stock == 0


def test_parse_rows_raises_clear_error_on_missing_columns():
    data = [
        ["SKU", "Name", "Qty"],
        ["PT-1421", "Лубрикатор", "22"],
    ]
    with pytest.raises(ValueError, match="missing required columns"):
        StockManager.parse_rows(data)


def test_parse_rows_empty_sheet_returns_no_products():
    assert StockManager.parse_rows([]) == []


# --- write_report ------------------------------------------------------

def test_write_report_creates_a_new_tab_when_the_title_is_free():
    manager = make_manager()
    manager.write_report("2026-09-11", HEADER, [["SKU-1", "name", "1"]])
    worksheet = manager.spreadsheet.worksheet("2026-09-11")
    assert worksheet.rows == [HEADER, ["SKU-1", "name", "1"]]


def test_write_report_replaces_rather_than_failing_on_a_rerun():
    # The real bug: a same-day rerun reuses the window-end title, and
    # add_worksheet (create_report) rejects the duplicate outright.
    existing = FakeWorksheet("2026-09-11")
    existing.rows = [HEADER, ["OLD-SKU", "stale", "9"]]
    manager = make_manager(worksheets=[existing])

    manager.write_report("2026-09-11", HEADER, [["NEW-SKU", "fresh", "1"]])

    assert existing.rows == [HEADER, ["NEW-SKU", "fresh", "1"]]


def test_write_report_leaves_no_mix_of_old_and_new_rows():
    existing = FakeWorksheet("2026-09-11")
    existing.rows = [HEADER, ["OLD-1", "a", "1"], ["OLD-2", "b", "2"]]
    manager = make_manager(worksheets=[existing])

    manager.write_report("2026-09-11", HEADER, [["NEW-1", "c", "3"]])

    assert "OLD-1" not in [row[0] for row in existing.rows]
    assert "OLD-2" not in [row[0] for row in existing.rows]
    assert existing.rows == [HEADER, ["NEW-1", "c", "3"]]
