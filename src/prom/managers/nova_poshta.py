import logging

from src.exceptions import PaymentOptionDisabledError, ReadyForDeliveryError
from src.models.delivery import Delivery
from src.models.order import Order
from src.models.order_status import OrderStatuses
from src.models.payment_option import PaymentOptions
from src.prom.exceptions import NotAllowedWarehouseException
from src.prom.managers.dummy import DummyManager


logger = logging.getLogger(__name__)


class NovaPoshtaManager(DummyManager):

    async def process_order(self, order: Order) -> Order:
        order = await super().process_order(order)

        if order.status in [
            OrderStatuses.CANCELED.value,
            OrderStatuses.DELIVERED.value,
        ]:
            return order

        if (
            order.status == OrderStatuses.PENDING.value and
            order.payment_option != PaymentOptions.CASH_ON_DELIVERY.value
        ):
            raise PaymentOptionDisabledError(order)

        if (data := order.delivery_provider_data):
            if data.declaration_number:
                raise ReadyForDeliveryError(order)

        delivery = None
        delivery_info = await self.scrape_client.generate_declaration(order)

        if delivery_info.get("status") == "error":
            raise NotAllowedWarehouseException(delivery_info["message"])
        delivery = Delivery.from_np_kwargs(**delivery_info["fields"])

        order = await self.receive_order(order)

        await self.notify(order, delivery)
        return order
