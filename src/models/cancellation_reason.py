from dataclasses import dataclass
from enum import Enum


@dataclass
class CancellationReason:
    name: str
    type: str
    title: str

    def __str__(self):
        return self.title

    def __eq__(self, other):
        return self.name == other.name


class CancellationReasons(Enum):
    REJECTED = CancellationReason(
        type="another",
        name="rejected",
        title="Відмова одержувача",
    )
    RETURNED = CancellationReason(
        type="another",
        name="returned",
        title="Повернуте відправникові",
    )

    @classmethod
    def get(cls, key):
        return cls[key.upper()]
