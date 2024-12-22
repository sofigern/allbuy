from dataclasses import dataclass
from enum import Enum


@dataclass
class PaymentOption:
    id: int
    name: str
    description: str | None = None

    def __str__(self):
        return f"{self.name}"

    def __eq__(self, other):
        return self.id == other.id


class PaymentOptions(Enum):
    PROM = PaymentOption(
        id=6943219,
        name="Пром-оплата",
        description="",
    )
    PARTS = PaymentOption(
        id=10061095,
        name="Оплатить частями",
        description="",
    )
    CASH_ON_DELIVERY = PaymentOption(
        id=8768054,
        name="Наложенный платеж",
        description="",
    )
