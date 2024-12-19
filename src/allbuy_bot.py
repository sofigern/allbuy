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
from src.prom.exceptions import GeneratingDeclarationException
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
        self.retry_orders = set()

    async def refresh_shop(self, orders: list[str]):
        logger.info("Refreshing shop data")
        input_orders = orders or []

        orders = await self.client.get_orders(status=OrderStatuses.PAID.value)
        processed_paid_orders = {}
        self.retry_orders = set()
        for order_data in orders:
            if input_orders and str(order_data["id"]) not in input_orders:
                continue

            order: Order = dacite.from_dict(
                Order, order_data,
                config=dacite.Config(
                    type_hooks={
                        OrderStatus: lambda s: OrderStatuses.get(s).value,
                    }
                )
            )
            processed_paid_orders[str(order.id)] = flatdict.FlatDict(asdict(order), delimiter=".")
            if (
                str(order.id) not in input_orders and
                str(order.id) in self.paid_orders
            ):
                processed_paid_orders[str(order.id)]["ts"] = self.paid_orders[str(order.id)]["ts"]
                continue
            
            order = await self.safe_refresh_order(order)
            if o := processed_paid_orders[str(order.id)]:
                o["ts"] = datetime.datetime.now().timestamp()
        
        self.paid_orders = {
            k: v for k, v in processed_paid_orders.items() 
            if k not in self.retry_orders
        }

        processed_pending_orders = {}
        self.retry_orders = set()
        orders = await self.client.get_orders(status=OrderStatuses.PENDING.value)

        for order_data in orders:
            if input_orders and str(order_data["id"]) not in input_orders:
                continue
            order: Order = dacite.from_dict(
                Order, order_data,
                config=dacite.Config(
                    type_hooks={
                        OrderStatus: lambda s: OrderStatuses.get(s).value,
                    }
                )
            )
            processed_pending_orders[str(order.id)] = flatdict.FlatDict(asdict(order), delimiter=".")
            if (
                str(order.id) not in input_orders and
                str(order.id) in self.pending_orders
            ):
                processed_pending_orders[str(order.id)]["ts"] = self.pending_orders[str(order.id)]["ts"]
                continue
            
            order = await self.safe_refresh_order(order)
            if o := processed_pending_orders[str(order.id)]:
                o["ts"] = datetime.datetime.now().timestamp()
    
        self.pending_orders = {
            k: v for k, v in processed_pending_orders.items()
            if k not in self.retry_orders
        }
    
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
        except e.GenerationDeclarationError as exc:
            self.retry_orders.add(str(order.id))
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
        try:
            order = await manager.process_order(order)
        except GeneratingDeclarationException as exc:
            raise e.GenerationDeclarationError(order) from exc

        return order
