from enum import Enum
from dataclasses import dataclass


@dataclass
class PaymentStatus:
    name: str
    title: str

    def __str__(self):
        return f"{self.title}"


class PaymentStatuses(Enum):

    UNPAID = PaymentStatus(
        name="unpaid",
        title="Очікує оплати",
    )
    PAID = PaymentStatus(
        name="paid",
        title="Оплачено",
    )
    PAID_OUT = PaymentStatus(
        name="paid_out",
        title="Виплачено",
    )
    REFUNDED = PaymentStatus(
        name="refunded",
        title="Виконано повернення",
    )

    UNDEFINED = PaymentStatus(
        name="undefined",
        title="Не визначено",
    )

    @classmethod
    def get(cls, key, default=None):
        try:
            return cls[key.upper()]
        except KeyError:
            return default
