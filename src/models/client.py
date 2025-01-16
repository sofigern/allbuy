from dataclasses import dataclass


@dataclass
class Client:
    id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.phone})"

    def __eq__(self, other):
        if self.id is None:
            return self.phone == other.phone
        return self.id == other.id
