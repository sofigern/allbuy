import aiohttp
import logging

from src.models.order import Order
from src.models.order_status import OrderStatus


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
    def order_url(self, order_id: int):
        return f"https://my.prom.ua/cms/order/edit/{order_id}"

    async def get_orders(
        self,
        status: OrderStatus | None = None,
    ):  
        params = {"limit": 100}
        if status:
            params["status"] = status.name

        async with self.client.get("orders/list", params=params) as resp:
            return (await resp.json()).get("orders", [])

    async def set_order_status(
        self,
        order: Order,
        status: OrderStatus,
    ) -> dict:
        logger.info("Setting order %s status to %s", order, status)
        async with self.client.post(
            "orders/set_status",
            json={
                "ids": [order.id],
                "status": status.name,
            },
        ) as resp:
            return (await resp.json())
