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
        name="Оплатити частинами",
        description="",
    )
    CASH_ON_DELIVERY = PaymentOption(
        id=8768054,
        name="Післяплата",
        description="",
    )
    CASH_ON_DELIVERY_HISTORICAL = PaymentOption(
        id=5001723,
        name="Післяплата",
        description="",
    )
    CASH_ON_DELIVERY_NOVA_POSHTA = PaymentOption(
        id=6146097,
        name='Післяплата "Нова Пошта"',
        description="",
    )
    CASH = PaymentOption(
        id=5001721,
        name="Готівкою",
        description="",
    )
    PRIVAT_BANK_CARD = PaymentOption(
        id=5001722,
        name="Оплата на карту Приват банку",
        description="",
    )
    NON_CASH_WITH_VAT = PaymentOption(
        id=5018050,
        name="Безготівковий розрахунок з ПДВ і без ПДВ",
        description="",
    )
