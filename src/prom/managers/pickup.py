import logging

from src.exceptions import PaymentOptionDisabledError, ReadyForDeliveryError
from src.models.delivery import Delivery
from src.models.order import Order
from src.models.order_status import OrderStatuses
from src.models.payment_option import PaymentOptions
from src.prom.exceptions import NotAllowedWarehouseException
from src.prom.managers.dummy import DummyManager


logger = logging.getLogger(__name__)


class PickupManager(DummyManager):

    async def process_order(self, order: Order) -> Order:
        order = await super().process_order(order)

        if order.status in [
            OrderStatuses.CANCELED.value,
            OrderStatuses.DELIVERED.value,
        ]:
            return order

        order = await self.receive_order(order)

        await self.notify(order)
        return order
