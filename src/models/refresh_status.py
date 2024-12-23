from dataclasses import dataclass


@dataclass
class RefreshStatus:
    order_id: int
    status: str
