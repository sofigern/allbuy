from dataclasses import replace
import datetime
import logging


from src.exceptions import (
    UnknownFinalizationError,
    IncompletePaymentError,
    ModifiedDateIsTooOldError,
)
from src.models.delivery import Delivery
from src.models.delivery_provider import DeliveryProviders
from src.models.delivery_status import DeliveryStatuses
from src.models.order import Order
from src.models.order_status import OrderStatuses
from src.models.payment_option import PaymentOptions
from src.models.payment_status import PaymentStatuses
from src.prom.client import PromAPIClient
from src.prom.remote.base import BaseScraperClient
from src.prom.managers.imanager import IManager


logger = logging.getLogger(__name__)


class DummyManager(IManager):

    def __init__(
        self,
        api_client: PromAPIClient,
        scrape_client: BaseScraperClient | None = None,
    ):
        self.api_client = api_client
        self.scrape_client = scrape_client

    async def notify(self, order: Order, delivery: Delivery | None = None) -> None:
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

        payment_status = ""
        if order.payment_data:
            payment_status = f"Статус оплати: {order.payment_data.status}\n"

        logger.info(
            "Замовлення %s було успішно %s\n"
            "------------------------------\n"
            "%s"
            "Cтатус замовлення: %s\n"
            "%s"
            "Спосіб оплати: %s\n"
            "%s"
            "Доставка (%s): %s\n"
            "%s"
            "------------------------------\n"
            "Деталі замовлення: %s",
            order, order.status, client_notes, order.status, delivery_status,
            order.payment_option, payment_status, order.delivery_option,
            order.delivery_address, delivery_str,
            PromAPIClient.order_url(order.id),
        )
