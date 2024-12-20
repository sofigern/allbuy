import logging

from src.models.order import Order
from src.prom.exceptions import OutdatedCookiesError
from src.prom.remote.base import BaseScraperClient


logger = logging.getLogger(__name__)


class RozetkaScraperClient(BaseScraperClient):
   
    async def generate_declaration(self, order: Order) -> dict:
        logger.info("Generating declaration for order %s", order)
        scraped_auth = await self.get_auth()
        delivery_info = await self._delivery_info(order, scraped_auth)
        return delivery_info
    
    async def _delivery_info(
        self,
        order: Order,
        scraped_auth: dict,
    ):
        async with self.client.post(
            "/remote/delivery/rozetka_delivery/create_declaration",
            headers=self.post_headers(
                order_id=order.id, 
                owner_id=scraped_auth["id"],
            ),
            json={
                "order_id": order.id,
            },
        ) as resp:
            if resp.content_type == "text/html":
                logger.error("Cookies are outdated. Clearing cookies and raising an exception.")
                self.client.cookie_jar.clear()
                raise OutdatedCookiesError
            return (await resp.json())
