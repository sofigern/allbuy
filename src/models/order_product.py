from dataclasses import dataclass


@dataclass(frozen=True)
class OrderProduct:
    """One line of an order, as returned inside ``/orders/list``.

    ``sku`` is Prom's "Код (артикул) товару" and is the key the owner's
    stock sheet is organised by; ``quantity`` is units of that line.
    """

    id: int | None = None
    external_id: str | None = None
    sku: str | None = None
    name: str | None = None
    quantity: float | None = None
    measure_unit: str | None = None
    price: str | None = None
    total_price: str | None = None
