import logging

from src.models.delivery import Delivery
from src.models.order import Order
from src.prom.managers.dummy import DummyManager


logger = logging.getLogger(__name__)


class NovaPoshtaManager(DummyManager):

    async def process_order(self, order: Order) -> Order:
        logger.info("%s is processing order %s", self.__class__, order)
        delivery = None
        # delivery_info = await self.scrape_client.generate_declaration(order)
        # delivery = Delivery.from_np_kwargs(**delivery_info["fields"])
        order = await self.receive_order(order)
        await self.notify(order, delivery)
        return order
