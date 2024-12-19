import datetime
import logging

from dataclasses import asdict
import dacite
import flatdict

import src.exceptions as e
from src.models.order import Order
from src.models.order_status import OrderStatus, OrderStatuses
from src.models.payment_option import PaymentOptions

from src.prom.client import PromAPIClient
from src.prom.managers.director import Director
from src.signal.bot import SignalBot


logger = logging.getLogger(__name__)


class AllBuyBot:

    def __init__(
        self, 
        client: PromAPIClient,
        messenger: SignalBot | None = None,
        cookies: str | None = None,
        paid_orders: dict | None = None,
        pending_orders: dict | None = None,
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
        self.paid_orders = paid_orders or dict()
        self.pending_orders = pending_orders or dict()

    async def refresh_shop(self):
        logger.info("Refreshing shop data")

        orders = await self.client.get_orders(status=OrderStatuses.PAID.value)
        processed_paid_orders = {}
        for order_data in orders:
            order: Order = dacite.from_dict(
                Order, order_data,
                config=dacite.Config(
                    type_hooks={
                        OrderStatus: lambda s: OrderStatuses.get(s).value,
                    }
                )
            )
            processed_paid_orders[str(order.id)] = flatdict.FlatDict(asdict(order), delimiter=".")
            if str(order.id) in self.paid_orders:
                processed_paid_orders[str(order.id)]["ts"] = self.paid_orders[str(order.id)]["ts"]
                continue
            
            order = await self.safe_refresh_order(order)
            processed_paid_orders[str(order.id)]["ts"] = datetime.datetime.now().timestamp()
        
        self.paid_orders = processed_paid_orders

        processed_pending_orders = {}
        orders = await self.client.get_orders(status=OrderStatuses.PENDING.value)
        for order_data in orders:
            order: Order = dacite.from_dict(
                Order, order_data,
                config=dacite.Config(
                    type_hooks={
                        OrderStatus: lambda s: OrderStatuses.get(s).value,
                    }
                )
            )
            processed_pending_orders[str(order.id)] = flatdict.FlatDict(asdict(order), delimiter=".")
            if str(order.id) in self.pending_orders:
                processed_pending_orders[str(order.id)]["ts"] = self.pending_orders[str(order.id)]["ts"]
                continue
            
            order = await self.safe_refresh_order(order)
            processed_pending_orders[str(order.id)]["ts"] = datetime.datetime.now().timestamp()
        self.pending_orders = processed_pending_orders
    
    async def safe_refresh_order(self, order: Order):
        try:
            order = await self.refresh_order(order)
        except (
            e.NotAllowedOrderStatusError,
            e.DeliveryProviderNotAllowedError,
            e.PaymentOptionDisabledError,
            e.IncompletePaymentError,
            e.ReadyForDeliveryError,
        ) as exc:
            logger.info("Sending message to the chat:\n%s", exc)
            if self.messenger:
                await self.messenger.send(str(exc))
        except e.ModifiedDateIsTooOldError as exc:
            logger.info("Ignoring too old orders:\n%s", exc)

        return order
       
    async def refresh_order(self, order: Order) -> Order:
        if (
            datetime.datetime.now() - 
            order.datetime_modified.replace(tzinfo=None)
        ) > datetime.timedelta(days=7):
            raise e.ModifiedDateIsTooOldError(order)
        
        if (
            order.status == OrderStatuses.PENDING.value and
            (
                order.payment_option == PaymentOptions.PROM.value or
                order.payment_option == PaymentOptions.PARTS.value
            )
        ):
            raise e.IncompletePaymentError(order)

        if order.status == OrderStatuses.PAID.value:
            if (data := order.delivery_provider_data):
                if data.declaration_number:
                    raise e.ReadyForDeliveryError(order)

        logger.info(f"Refreshing order %s", order)

        manager = self.director.assign(order)
        order = await manager.process_order(order)
        return order
