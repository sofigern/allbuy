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

            payment_status = ""
            if order.payment_data:
                payment_status = f"Статус оплати: {order.payment_data.status}\n"

            await self.messenger.send(
                f"Замовлення {order} було успішно {order.status}" + "\n" +
                "------------------------------" + "\n" +
                client_notes +
                f"Cтатус замовлення: {order.status}" + "\n" +
                delivery_status +
                f"Спосіб оплати: {order.payment_option}" + "\n" +
                payment_status +
                f"Доставка ({order.delivery_option}): {order.delivery_address}" + "\n" +
                delivery_str +
                "------------------------------" + "\n" +
                f"Деталі замовлення: {PromAPIClient.order_url(order.id)}"
            )

    async def receive_order(self, order: Order) -> Order:
        if order.status == OrderStatuses.PENDING.value:
            await self.api_client.set_order_status(order, OrderStatuses.RECEIVED.value)
            order = replace(order, status=OrderStatuses.RECEIVED.value)
        return order

    async def cancel_order(
        self,
        order: Order,
        cancellation_reason: str,
        cancellation_text: str | None = None,
    ) -> Order:
        await self.api_client.set_order_status(
            order, OrderStatuses.CANCELED.value,
            cancellation_reason=cancellation_reason,
            cancellation_text=cancellation_text,
        )

        order = replace(order, status=OrderStatuses.CANCELED.value)
        return order

    async def finalize_order(self, order: Order) -> Order:
        await self.api_client.set_order_status(order, OrderStatuses.DELIVERED.value)
        order = replace(order, status=OrderStatuses.DELIVERED.value)
        return order

    async def cancellation_hook(self, order: Order) -> Order:
        logger.info("Checking if order %s can be canceled", order)

        if (
            order.age > datetime.timedelta(days=60) and
            order.delivery_provider_data and
            (status := order.delivery_provider_data.unified_status) in [
                DeliveryStatuses.RETURNED.value.name,
                DeliveryStatuses.REJECTED.value.name,
            ]
        ):
            order = await self.cancel_order(
                order,
                cancellation_reason="another",
                cancellation_text=DeliveryStatuses.get(status).value.title
            )
            await self.notify(order)
            return order

        if (
            order.age > datetime.timedelta(days=60) and
            order.payment_data and
            (status := order.payment_data.status) in [
                PaymentStatuses.REFUNDED.value,
            ]
        ):
            order = await self.cancel_order(
                order,
                cancellation_reason="another",
                cancellation_text=status.title
            )
            await self.notify(order)
            return order

        if (
            order.status == OrderStatuses.PENDING.value and
            order.payment_option in [
                PaymentOptions.PROM.value,
                PaymentOptions.PARTS.value,
            ]
        ):
            if order.age > datetime.timedelta(days=60):
                order = await self.cancel_order(
                    order,
                    cancellation_reason="payment_not_received",
                )
                await self.notify(order)
                return order

            raise IncompletePaymentError(order)

        if order.status == OrderStatuses.RECEIVED.value:
            # if order.datetime_created.date() < datetime.date(2020, 1, 1):
            #     order = await self.finalize_order(order)
            # el
            if (
                (
                    order.payment_option is None or
                    order.payment_option in [
                        PaymentOptions.CASH.value,
                        PaymentOptions.CASH_ON_DELIVERY.value,
                        PaymentOptions.CASH_ON_DELIVERY_HISTORICAL.value,
                        PaymentOptions.CASH_ON_DELIVERY_NOVA_POSHTA.value,
                        PaymentOptions.PRIVAT_BANK_CARD.value,
                        PaymentOptions.NON_CASH_WITH_VAT.value,
                    ]
                ) and
                order.delivery_provider_data and
                (
                    order.delivery_provider_data.unified_status in [
                        DeliveryStatuses.DELIVERED_CASH_CRUISE.value.name,
                        DeliveryStatuses.DELIVERED_CASH_RECEIVED.value.name,
                    ] or
                    (
                        order.delivery_provider_data.unified_status in [
                            DeliveryStatuses.DELIVERED.value.name
                        ] and
                        order.delivery_option in [
                            DeliveryProviders.MEEST.value,
                            DeliveryProviders.UKR_POSHTA.value,
                            DeliveryProviders.NOVA_POSHTA.value,
                        ]
                    )
                )
            ):
                order = await self.finalize_order(order)
                await self.notify(order)
                return order

        if order.age > datetime.timedelta(days=7):
            raise ModifiedDateIsTooOldError(order)

        if order.status == OrderStatuses.RECEIVED.value:
            raise UnknownFinalizationError(order)

        return order

    async def process_order(self, order: Order, initial: bool = False) -> Order:
        logger.info("%s is processing order %s", self.__class__, order)
        order = await self.cancellation_hook(order)
        return order
