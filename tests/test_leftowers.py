from src.models.product import Product

from leftowers import normalize_sku, plan_updates


def prom(sku, presence="available", price=100.0, id=1):
    return Product(id=id, sku=sku, name=f"prom {sku}", presence=presence, price=price)


def stock(sku, quantity):
    return Product(sku=sku, name=f"stock {sku}", quantity_in_stock=quantity, price=90.0)


def intertool(sku, in_stock, price=50.0):
    return Product(sku=sku, name=f"intertool {sku}", in_stock=in_stock, price=price)


def test_sheet_only_availability_keeps_product_available():
    # The TC-7635 case: 35 units on the owner's sheet, but the intertool
    # b2c feed says available="false". The sheet must win.
    updates, unknown = plan_updates(
        prom_products=[prom("TC-7635")],
        stock_products=[stock("TC-7635", quantity=35)],
        intertool_products=[intertool("TC-7635", in_stock=False)],
    )
    assert updates == []
    assert unknown == []


def test_sheet_only_availability_flips_not_available_back():
    updates, unknown = plan_updates(
        prom_products=[prom("TC-7635", presence="not_available")],
        stock_products=[stock("TC-7635", quantity=35)],
        intertool_products=[intertool("TC-7635", in_stock=False)],
    )
    assert unknown == []
    [(old, new)] = updates
    assert old.presence == "not_available"
    assert new.presence == "available"
    assert new.in_stock is True


def test_sheet_sku_with_stray_whitespace_still_matches():
    # Regression for the actual production bug: the sheet cell held
    # "TC-7635\n\n", which never matched prom's clean "TC-7635", so a
    # product with 35 units was reported as out of stock.
    updates, unknown = plan_updates(
        prom_products=[prom("TC-7635")],
        stock_products=[stock("TC-7635\n\n", quantity=35)],
        intertool_products=[intertool("TC-7635", in_stock=False)],
    )
    assert updates == []
    assert unknown == []


def test_feed_only_availability_keeps_product_available():
    updates, unknown = plan_updates(
        prom_products=[prom("HT-0001", price=50.0)],
        stock_products=[stock("HT-0001", quantity=0)],
        intertool_products=[intertool("HT-0001", in_stock=True, price=40.0)],
    )
    assert updates == []
    assert unknown == []


def test_available_on_both_sources_stays_available():
    updates, unknown = plan_updates(
        prom_products=[prom("HT-0002", price=50.0)],
        stock_products=[stock("HT-0002", quantity=3)],
        intertool_products=[intertool("HT-0002", in_stock=True, price=40.0)],
    )
    assert updates == []
    assert unknown == []


def test_available_on_neither_source_flips_to_not_available():
    updates, unknown = plan_updates(
        prom_products=[prom("HT-0003")],
        stock_products=[stock("HT-0003", quantity=0)],
        intertool_products=[intertool("HT-0003", in_stock=False)],
    )
    assert unknown == []
    [(old, new)] = updates
    assert old.presence == "available"
    assert new.presence == "not_available"
    assert new.in_stock is False


def test_sku_absent_from_both_sources_is_unknown():
    product = prom("XX-9999")
    updates, unknown = plan_updates(
        prom_products=[product],
        stock_products=[stock("HT-0001", quantity=5)],
        intertool_products=[intertool("HT-0002", in_stock=True)],
    )
    assert updates == []
    assert unknown == [product]


def test_normalize_sku():
    assert normalize_sku("TC-7635\n\n") == "TC-7635"
    assert normalize_sku("\n HT-0403") == "HT-0403"
    assert normalize_sku("TC-7635") == "TC-7635"
    assert normalize_sku(None) is None
    assert normalize_sku("") == ""
