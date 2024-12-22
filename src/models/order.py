import datetime
from dataclasses import dataclass, field

from src.models.client import Client
from src.models.delivery_provider import DeliveryProvider
from src.models.delivery_provider_data import DeliveryProviderData
from src.models.order_status import OrderStatus
from src.models.payment_option import PaymentOption


@dataclass(frozen=True)
class Order:
    id: int
    status: OrderStatus
    price: str
    date_created: str
    date_modified: str
    delivery_address: str
    delivery_option: DeliveryProvider
    payment_option: PaymentOption
    client: Client
    client_notes: str
    delivery_provider_data: DeliveryProviderData | None = None
    phone: str = field(repr=False, default="")

    def __post_init__(self, **kwargs):
        self.client.phone = self.phone

    @property
    def datetime_created(self) -> datetime.datetime | None:
        if self.date_created is None:
            return None
        return datetime.datetime.fromisoformat(self.date_created)
    
    @property
    def datetime_modified(self) -> datetime.datetime | None:
        if self.date_modified is None:
            return None
        return datetime.datetime.fromisoformat(self.date_modified)

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
