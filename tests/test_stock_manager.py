import pytest

from src.stock.stock_manager import StockManager

HEADER = ["Артикул", "Товар", "Кількість", "Од.", "МРРЦ", "Базова", "Ціна", "Сума"]


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
