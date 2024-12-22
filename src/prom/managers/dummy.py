from dataclasses import replace
import logging

from src.models.delivery import Delivery
from src.models.delivery_provider import DeliveryProviders
from src.models.delivery_status import DeliveryStatuses
from src.models.order import Order
from src.models.order_status import OrderStatuses
from src.models.payment_option import PaymentOptions
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

            client_notes = ""
            if order.client_notes:
                client_notes = f"Коментар: {order.client_notes}\n"

            delivery_status = ""
            if (
                order.delivery_provider_data and
                (status := order.delivery_provider_data.unified_status)
            ):
                delivery_status = f"Статус доставки: {DeliveryStatuses.get(status).value}\n"

            await self.messenger.send(
                f"Замовлення {order} було успішно {order.status}" + "\n" +
                "------------------------------" + "\n" +
                client_notes +
                f"Cтатус замовлення: {order.status}" + "\n" +
                delivery_status +
                f"Спосіб оплати: {order.payment_option}" + "\n" +
                f"Доставка ({order.delivery_option}): {order.delivery_address}" + "\n" +
                delivery_str +
                "------------------------------" + "\n" +
                f"Деталі замовлення: {PromAPIClient.order_url(order.id)}"
            )

    async def receive_order(self, order: Order) -> Order:
        await self.api_client.set_order_status(order, OrderStatuses.RECEIVED.value)
        order = replace(order, status=OrderStatuses.RECEIVED.value)
        return order

    async def finalize_order(self, order: Order) -> Order:
        await self.api_client.set_order_status(order, OrderStatuses.DELIVERED.value)
        order = replace(order, status=OrderStatuses.DELIVERED.value)
        return order

    async def process_order(self, order: Order) -> Order:
        logger.info("%s is processing order %s", self.__class__, order)

        if order.status == OrderStatuses.RECEIVED.value:
            if (
                order.payment_option == PaymentOptions.CASH_ON_DELIVERY.value and
                (
                    order.delivery_provider_data.unified_status in [
                        DeliveryStatuses.DELIVERED_CASH_CRUISE.value.name,
                        DeliveryStatuses.DELIVERED_CASH_RECEIVED.value.name,
                    ] or
                    (
                        order.delivery_provider_data.unified_status in [
                            DeliveryStatuses.DELIVERED.value.name
                        ] and
                        order.delivery_option == DeliveryProviders.UKR_POSHTA.value
                    )
                )
            ):
                order = await self.finalize_order(order)
        elif order.status == OrderStatuses.PENDING.value:
            order = await self.receive_order(order)

        await self.notify(order)
        return order
