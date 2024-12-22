import logging

from src.models.order import Order
from src.prom.exceptions import OutdatedCookiesError
from src.prom.remote.base import BaseScraperClient


logger = logging.getLogger(__name__)


class UkrPoshtaScraperClient(BaseScraperClient):

    async def generate_declaration(self, order: Order) -> dict:
        logger.info("Generating declaration for order %s", order)
        scraped_auth = await self.get_auth()
        scraped_order = await self.get_order(order)
        init_data_order = await self._init_data_order(order)
        delivery_info = await self._delivery_info(
            order,
            scraped_auth,
            scraped_order,
            init_data_order,
        )
        return delivery_info

    async def _init_data_order(
        self,
        order: Order,
    ):
        async with self.client.get(
            "/remote/delivery/ukrposhta/init_data_order",
            params={
                "order_id": order.id,
                "delivery_option_id": order.delivery_option.id,
            }
        ) as resp:
            if resp.content_type == "text/html":
                logger.error("Cookies are outdated. Clearing cookies and raising an exception.")
                self.client.cookie_jar.clear()
                raise OutdatedCookiesError
            return (await resp.json())["data"]

    async def _delivery_info(
        self,
        order: Order,
        scraped_auth: dict,
        scraped_order: dict,
        init_data_order: dict,
    ):
        default_price = scraped_order["cartTotalPriceInDefaultCurrency"]

        request = {
            "order_id": order.id,
            "delivery_option_id": str(order.delivery_option.id),
            "cart_total_price": init_data_order.get("cod_amount", default_price),
        }

        async with self.client.post(
            "/remote/new_delivery/ukrposhta/generate_declaration",
            headers=self.post_headers(order_id=order.id, owner_id=scraped_auth["id"]),
            json=request,
        ) as resp:
            if resp.content_type == "text/html":
                logger.error("Cookies are outdated. Clearing cookies and raising an exception.")
                self.client.cookie_jar.clear()
                raise OutdatedCookiesError
            return await resp.json()
