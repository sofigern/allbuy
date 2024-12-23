from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class OrderStatus:
    id: int
    name: str
    title: str

    def __str__(self):
        return self.title

    def __eq__(self, other):
        return self.name == other.name


class OrderStatuses(Enum):
    PENDING = OrderStatus(id=0, title="Нове", name="pending")
    RECEIVED = OrderStatus(id=1, title="Прийняте", name="received")
    DELIVERED = OrderStatus(id=3, title="Виконане", name="delivered")
    CANCELED = OrderStatus(id=4, title="Скасоване", name="canceled")
    PAID = OrderStatus(id=6, title="Оплачене", name="paid")

    @classmethod
    def get(cls, key):
        return cls[key.upper()]
