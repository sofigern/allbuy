import logging

import aiohttp
import dacite

from src.models.order import Order
from src.models.order_status import OrderStatus, OrderStatuses
from src.models.payment_status import PaymentStatus, PaymentStatuses
from src.models.product import Product


logger = logging.getLogger(__name__)


class PromAPIClient:
    def __init__(
        self,
        token: str,
        base_url: str = "https://my.prom.ua/api/v1/",
    ):
        self.base_url = base_url
        self.token = token

        self.client = aiohttp.ClientSession(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
        )

    @classmethod
    def order_url(cls, order_id: int):
        return f"https://my.prom.ua/cms/order/edit/{order_id}"

    async def get_products(self) -> list[Product]:
        products = []
        has_more = True
        while has_more:
            params = {"limit": 100}
            if products:
                params["last_id"] = products[-1].id

            async with self.client.get("products/list", params=params) as resp:
                response_json = await resp.json()

            if not response_json.get("products"):
                has_more = False
            else:
                products += [
                    dacite.from_dict(Product, product_data)
                    for product_data in response_json.get("products")
                ]

        return products

    async def edit_products(self, products: list[Product]) -> dict:
        logger.info("Updating products %s", products)

        body = [
            {
                "id": product.id,
                "price": product.price,
                "presence": product.presence,
                "in_stock": product.in_stock,
            }
            for product in products
        ]

        async with self.client.post(
            "products/edit",
            json=body,
        ) as resp:
            return await resp.json()

    async def get_orders(
        self,
        status: OrderStatus | None = None,
        date_to: str | None = None,
    ) -> list[Order]:
        params = {"limit": 100}

        if date_to:
            params["date_to"] = date_to

        if status:
            params["status"] = status.name

        logger.info("Getting orders with params: %s", params)

        async with self.client.get("orders/list", params=params) as resp:
            response_json = await resp.json()

        return [
            dacite.from_dict(
                Order, order_data,
                config=dacite.Config(
                    type_hooks={
                        OrderStatus: lambda s: OrderStatuses.get(s).value,
                        PaymentStatus: lambda s:
                            PaymentStatuses.get(s, PaymentStatuses.UNDEFINED).value,
                    }
                )
            )
            for order_data in response_json.get("orders", [])
        ]

    async def set_order_status(
        self,
        order: Order,
        status: OrderStatus,
        cancellation_reason: str | None = None,
        cancellation_text: str | None = None,
    ) -> dict:
        logger.info("Setting order %s status to %s", order, status)

        request_data = {
            "ids": [order.id],
            "status": status.name,
        }

        if cancellation_reason:
            request_data["cancellation_reason"] = cancellation_reason

        if cancellation_text:
            request_data["cancellation_text"] = cancellation_text

        async with self.client.post(
            "orders/set_status",
            json=request_data,
        ) as resp:
            return await resp.json()
