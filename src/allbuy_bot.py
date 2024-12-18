import datetime
import logging

import dacite

import src.exceptions as e
from src.models.order import Order
from src.models.order_status import OrderStatus, OrderStatuses
from src.models.payment_option import PaymentOptions

from src.prom.client import PromAPIClient
from src.prom.managers.director import Director
from src.signal.bot import SignalBot


logger = logging.getLogger(__name__)


class AllBuyBot:
    
    ALLOWED_STATUSES = [OrderStatuses.PENDING.value]
    DISABLED_PAYMENT_OPTIONS = [PaymentOptions.PROM.value, PaymentOptions.PARTS.value]

    def __init__(
        self, 
        client: PromAPIClient,
        messenger: SignalBot | None = None,
        cookies: str | None = None,
        processed_orders: dict | None = None,
    ):
        self.client = client
        self.orders = []
        self.processed_orders = set()
        self.messenger = messenger
        self.director = Director(
            api_client=self.client,
            messenger=self.messenger,
            cookies=cookies,
        )
        self.processed_orders = processed_orders or dict()

    async def refresh_shop(self):
        logger.info("Refreshing shop data")
        self.orders = await self.client.get_orders(status=OrderStatuses.PENDING.value)

        for order_data in self.orders:
            order = dacite.from_dict(
                Order, order_data,
                config=dacite.Config(
                    type_hooks={
                        OrderStatus: lambda s: OrderStatuses.get(s).value,
                    }
                )
            )
            if str(order.id) in self.processed_orders:
                continue

            try:
                order = await self.refresh_order(order)
            except e.NotAllowedOrderStatusError as exc:
                logger.info("Sending message to the chat:\n%s", exc)
                if self.messenger:
                    await self.messenger.send(str(exc))
            except e.DeliveryProviderNotAllowedError as exc:
                logger.info("Sending message to the chat:\n%s", exc)
                if self.messenger:
                    await self.messenger.send(str(exc))
            except e.PaymentOptionDisabledError as exc:
                logger.info("Sending message to the chat:\n%s", exc)
                if self.messenger:
                    await self.messenger.send(str(exc))
            except e.ModifiedDateIsTooOldError as exc:
                logger.info("Sending message to the chat:\n%s", exc)
                if self.messenger:
                    await self.messenger.send(str(exc))
            finally:
                self.processed_orders[str(order.id)] = {"ts": datetime.datetime.now().timestamp()}

    async def refresh_order(self, order: Order) -> Order:
        if (
            datetime.datetime.now() - 
            order.datetime_modified.replace(tzinfo=None)
        ) > datetime.timedelta(days=7):
            raise e.ModifiedDateIsTooOldError(order)
        
        if order.status not in self.ALLOWED_STATUSES:
            raise e.NotAllowedOrderStatusError(order)
        
        if order.payment_option in self.DISABLED_PAYMENT_OPTIONS:
            raise e.PaymentOptionDisabledError(order,)

        logger.info(f"Refreshing order %s", order)

        manager = self.director.assign(order)
        order = await manager.process_order(order)
        return order
