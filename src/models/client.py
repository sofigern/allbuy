from dataclasses import dataclass
from enum import Enum


@dataclass
class Client:
    id: int
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.phone})"
    
    def __eq__(self, other):
        return self.id == other.id
