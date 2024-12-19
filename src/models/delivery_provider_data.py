from dataclasses import dataclass


@dataclass(frozen=True)
class DeliveryProviderData:
    provider: str | None = None
    type: str | None = None
    sender_warehouse_id: str | None = None
    recipient_warehouse_id: str | None = None
    declaration_number: str | None = None
    unified_status: str | None = None
