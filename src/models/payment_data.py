from dataclasses import dataclass


from src.models.payment_status import PaymentStatus


@dataclass
class PaymentData:
    type: str | None
    status: PaymentStatus | None
    status_modified: str | None = None
