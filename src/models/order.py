import datetime
from dataclasses import dataclass, field

from src.clock import now_kyiv, to_kyiv
from src.models.client import Client
from src.models.delivery_provider import DeliveryProvider
from src.models.delivery_provider_data import DeliveryProviderData
from src.models.order_product import OrderProduct
from src.models.order_status import OrderStatus
from src.models.payment_option import PaymentOption
from src.models.payment_data import PaymentData


@dataclass(frozen=True)
class Order:
    id: int
    status: OrderStatus
    price: str
    date_created: str
    date_modified: str
    delivery_address: str
    delivery_option: DeliveryProvider | None
    client: Client
    products: list[OrderProduct] = field(default_factory=list)
    client_notes: str | None = None
    payment_option: PaymentOption | None = None
    payment_data: PaymentData | None = None
    delivery_provider_data: DeliveryProviderData | None = None
    phone: str = field(repr=False, default="")

    def __post_init__(self, **kwargs):
        self.client.phone = self.phone

    @property
    def datetime_created(self) -> datetime.datetime | None:
        # Aware Europe/Kyiv. Prom sends an offset here; dropping it made
        # every age below wrong by that offset on a non-Kyiv host.
        return to_kyiv(self.date_created)

    @property
    def datetime_modified(self) -> datetime.datetime | None:
        return to_kyiv(self.date_modified)

    @property
    def age(self) -> datetime.timedelta:
        return now_kyiv() - self.datetime_created

    def __str__(self):
        return (
            f"{self.id} ({self.datetime_created.date().isoformat()}): {self.price} "
            f"від {self.client}"
        )

    def to_text(self):
        client_notes = ""
        if self.client_notes:
            client_notes = (
                "------------------------------\n"
                f"Коментар: {self.client_notes}\n"
            )
        return (
            f"{self}\n" +
            client_notes
        )

    def __eq__(self, other):
        return self.id == other.id
