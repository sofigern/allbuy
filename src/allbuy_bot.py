import datetime
import logging

from dataclasses import asdict
import flatdict

import src.exceptions as e
from src.models.order import Order
from src.models.order_status import OrderStatuses

from src.prom.client import PromAPIClient
from src.prom.exceptions import GeneratingDeclarationException, NotAllowedWarehouseException
from src.prom.managers.director import Director, DummyManager
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
        admin_phone: str | None = None,
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
        self.admin_phone = admin_phone

    async def refresh_shop(self, orders: list[str]):
        logger.info("Refreshing shop data")
        input_orders = orders or []

        # processing = True
        date_to = None
        # while processing:
        orders = await self.client.get_orders(status=OrderStatuses.RECEIVED.value, date_to=date_to)

            # if not orders:
            #     processing = False
            #     break

        for order in orders:
            if input_orders and str(order.id) not in input_orders:
                continue
            # date_to = order.datetime_created.strftime("%Y-%m-%dT%H:%M:%S")
            await self.safe_refresh_order(order)

        orders = await self.client.get_orders(status=OrderStatuses.PAID.value)
        processed_paid_orders = {}
        self.retry_orders = set()
        for order in orders:
            if input_orders and str(order.id) not in input_orders:
                continue

            processed_paid_orders[str(order.id)] = flatdict.FlatDict(asdict(order), delimiter=".")
            initial = str(order.id) not in self.paid_orders

            if not initial:
                processed_paid_orders[str(order.id)]["ts"] = self.paid_orders[str(order.id)]["ts"]

            order = await self.safe_refresh_order(order, initial=initial)
            if o := processed_paid_orders[str(order.id)]:
                o["ts"] = datetime.datetime.now().timestamp()

        self.paid_orders = {
            k: v for k, v in processed_paid_orders.items()
            if k not in self.retry_orders
        }

        processed_pending_orders = {}
        self.retry_orders = set()
        orders = await self.client.get_orders(status=OrderStatuses.PENDING.value)

        for order in orders:
            if input_orders and str(order.id) not in input_orders:
                continue

            processed_pending_orders[str(order.id)] = (
                flatdict.FlatDict(asdict(order), delimiter=".")
            )
            initial = str(order.id) not in self.pending_orders
            if not initial:
                processed_pending_orders[str(order.id)]["ts"] = (
                    self.pending_orders[str(order.id)]["ts"]
                )

            order = await self.safe_refresh_order(order, initial=initial)
            if o := processed_pending_orders[str(order.id)]:
                o["ts"] = datetime.datetime.now().timestamp()

        self.pending_orders = {
            k: v for k, v in processed_pending_orders.items()
            if k not in self.retry_orders
        }

    async def safe_refresh_order(self, order: Order, initial: bool = False) -> Order:
        try:
            order = await self.refresh_order(order, initial=initial)
        except (
            e.NotAllowedOrderStatusError,
            e.DeliveryProviderNotAllowedError,
            e.PaymentOptionDisabledError,
            e.IncompletePaymentError,
            e.ReadyForDeliveryError,
        ) as exc:
            logger.info("Sending message to the chat:\n%s", exc)
            if self.messenger and initial:
                await self.messenger.send(str(exc))
        except e.DeliveryProviderError as exc:
            logger.info("Sending message to the chat:\n%s", exc)
            if self.messenger and initial:
                await self.messenger.send(str(exc), notify=[self.admin_phone])
        except e.GenerationDeclarationError as exc:
            self.retry_orders.add(str(order.id))
            logger.info("Sending message to the chat:\n%s", exc)
            if self.messenger and initial:
                await self.messenger.send(str(exc))
        except e.ModifiedDateIsTooOldError as exc:
            logger.info("Ignoring too old orders:\n%s", exc)
        except e.UnknownFinalizationError as exc:
            logger.exception("Unknown finalization error:\n%s", exc)

        return order

    async def refresh_order(self, order: Order, initial: bool = False) -> Order:
        logger.info("Refreshing order %s", order)

        manager = self.director.assign(order)
        try:
            order = await manager.process_order(order, initial=initial)
        except GeneratingDeclarationException as exc:
            logger.exception("Error while generating declaration for order")
            raise e.GenerationDeclarationError(order) from exc
        except NotAllowedWarehouseException as exc:
            logger.exception("Error while generating declaration for order")
            raise e.DeliveryProviderError(order=order) from exc
        else:
            if initial and type(manager) is DummyManager:
                raise e.DeliveryProviderNotAllowedError(order)

        return order
