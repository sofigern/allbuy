from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class DeliveryProvider:
    id: int
    name: str
    comment: str | None
    type: str | None = None
    enabled: bool | None = None

    def __str__(self):
        return f"{self.name}"

    def __eq__(self, other):
        return self.id == other.id


class DeliveryProviders(Enum):
    NOVA_POSHTA = DeliveryProvider(
        id=9062118,
        enabled=True,
        type="nova_poshta",
        name="Нова Пошта",
        comment=None,
    )
    PICKUP = DeliveryProvider(
        id=9062114,
        enabled=True,
        type="pickup",
        name="Самовивіз",
        comment=None,
    )
    UKR_POSHTA = DeliveryProvider(
        id=9776215,
        enabled=True,
        type="ukrposhta",
        name="Укрпошта",
        comment=None,
    )
    ROZETKA = DeliveryProvider(
        id=15330563,
        enabled=True,
        type="rozetka_delivery",
        name="Магазини Rozetka",
        comment=None,
    )
    MEEST = DeliveryProvider(
        id=12799845,
        enabled=True,
        type="meest",
        name="Meest ПОШТА",
        comment=None,
    )
    JUSTIN = DeliveryProvider(
        id=12799844,
        enabled=True,
        type="justin",
        name='Доставка "Justin"',
        comment=None,
    )
