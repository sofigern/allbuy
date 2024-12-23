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
    CASH_ON_DELIVERY_HISTORICAL = PaymentOption(
        id=5001723,
        name="Наложенный платеж",
        description="",
    )
    CASH_ON_DELIVERY_NOVA_POSHTA = PaymentOption(
        id=6146097,
        name='Наложенный платеж "Нова Пошта"',
        description="",
    )
    CASH = PaymentOption(
        id=5001721,
        name="Наличными",
        description="",
    )
    PRIVAT_BANK_CARD = PaymentOption(
        id=5001722,
        name="Оплата на карту Приват банка",
        description="",
    )
    NON_CASH_WITH_VAT = PaymentOption(
        id=5018050,
        name="Безналичный расчет с НДС и без НДС",
        description="",
    )
