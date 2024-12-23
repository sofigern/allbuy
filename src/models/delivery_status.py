from dataclasses import dataclass
from enum import Enum


@dataclass
class DeliveryStatus:
    id: int | None
    name: str
    title: str

    def __str__(self):
        return self.title

    def __eq__(self, other):
        return self.name == other.name


class DeliveryStatuses(Enum):
    DELIVERED_CASH_CRUISE = DeliveryStatus(
        id=None,
        title="Отримано. Очікуйте SMS про надходження грошового переказу",
        name="delivered_cash_cruise",
    )
    DELIVERED_CASH_RECEIVED = DeliveryStatus(
        id=None,
        title="Отримано. Грошовий переказ видано",
        name="delivered_cash_received",
    )
    DELIVERED = DeliveryStatus(
        id=None,
        title="Отримано",
        name="delivered",
    )

    REJECTED = DeliveryStatus(
        id=None,
        title="Відмова одержувача",
        name="rejected",
    )
    RETURNED = DeliveryStatus(
        id=None,
        title="Повернуте відправникові",
        name="returned",
    )

    @classmethod
    def get(cls, key):
        return cls[key.upper()]
