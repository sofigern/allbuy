from dataclasses import dataclass
from enum import Enum


@dataclass
class OrderStatus:
    id: int
    name: str
    title: str

    def __str__(self):
        return f"{self.title}"
    
    def __eq__(self, other):
        return self.name == other.name


class OrderStatuses(Enum):
    PENDING = OrderStatus(id=0, title="Новый", name="pending")
    RECEIVED = OrderStatus(id=1, title="Принят", name="received")
    DELIVERED = OrderStatus(id=3, title="Выполнен", name="delivered")
    CANCELED = OrderStatus(id=4, title="Отменен", name="canceled")
    PAID = OrderStatus(id=6, title="Оплаченный", name="paid")

    @classmethod
    def get(cls, key):
        return cls[key.upper()]
