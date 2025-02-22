import datetime
from dataclasses import dataclass


@dataclass
class Product:
    id: int | None = None
    sku: str | None = None
    name: str | None = None
    presence: str | None = None
    price: int | float | None = None
    currency: str | None = None
    status: str | None = None
    quantity_in_stock: int | None = None
    in_stock: bool | None = None
    date_modified: str | None = None

    @property
    def datetime_modified(self) -> datetime.datetime | None:
        if self.date_modified is None:
            return None
        return datetime.datetime.fromisoformat(self.date_modified).replace(tzinfo=None)

    @property
    def url(self) -> str | None:
        if self.id is None:
            return None
        return f"https://my.prom.ua/cms/product/edit/{self.id}"
