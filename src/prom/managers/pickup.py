import logging

from src.models.order import Order
from src.models.order_status import OrderStatuses
from src.prom.managers.dummy import DummyManager


logger = logging.getLogger(__name__)


class PickupManager(DummyManager):

    async def process_order(self, order: Order, initial: bool = False) -> Order:
        order = await super().process_order(order, initial=initial)

        if order.status in [
            OrderStatuses.CANCELED.value,
            OrderStatuses.DELIVERED.value,
        ]:
            return order

        if not initial:
            return order

        order = await self.receive_order(order)

        await self.notify(order)
        return order
