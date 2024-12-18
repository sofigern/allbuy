from dataclasses import replace
import logging

from src.models.delivery import Delivery
from src.models.order import Order
from src.models.order_status import OrderStatuses
from src.prom.client import PromAPIClient
from src.prom.remote.base import BaseScraperClient
from src.prom.managers.imanager import IManager
from src.signal.bot import SignalBot


logger = logging.getLogger(__name__)


class DummyManager(IManager):

    def __init__(
        self, 
        api_client: PromAPIClient,
        scrape_client: BaseScraperClient | None = None,
        messenger: SignalBot | None = None,
    ):
        self.api_client = api_client
        self.scrape_client = scrape_client
        self.messenger = messenger

    async def notify(self, order: Order, delivery: Delivery | None = None) -> None:
        if self.messenger:
            delivery_str = ""
            if delivery:
                delivery_str = f"ЕН {delivery.number} Вартість: {delivery.cost or 'Не визначена'}\n"

            await self.messenger.send(
                f"Замовлення {order} було успішно оброблено" + "\n"
                "------------------------------" + "\n"
                f"Cтатус замовлення: {order.status}" + "\n"
                f"Доставка ({order.delivery_option}): {order.delivery_address}" + "\n"
                f"{delivery_str}"
                "------------------------------" + "\n"
                f"Деталі замовлення: {PromAPIClient.order_url(order.id)}"
            )

    async def receive_order(self, order: Order) -> Order:
        # await self.api_client.set_order_status(order, OrderStatuses.RECEIVED.value)
        order = replace(order, status=OrderStatuses.RECEIVED.value)
        return order

    async def process_order(self, order: Order) -> Order:
        logger.info("%s is processing order %s", self.__class__, order)
        order = await self.receive_order(order)
        await self.notify(order)
        return order
