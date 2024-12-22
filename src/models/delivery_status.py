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
        title="Получено. Ожидайте SMS о поступлении денежного перевода",
        name="delivered_cash_cruise",
    )
    DELIVERED_CASH_RECEIVED = DeliveryStatus(
        id=None,
        title="Получено. Денежный перевод выдан",
        name="delivered_cash_received",
    )
    DELIVERED = DeliveryStatus(
        id=None,
        title="Получено",
        name="delivered",
    )

    @classmethod
    def get(cls, key):
        return cls[key.upper()]
