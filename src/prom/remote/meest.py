import logging

from src.models.order import Order
from src.prom.exceptions import OutdatedCookiesError, GeneratingDeclarationException
from src.prom.remote.base import BaseScraperClient


logger = logging.getLogger(__name__)


class MeestScraperClient(BaseScraperClient):

    async def generate_declaration(self, order: Order) -> dict:
        logger.info("Generating declaration for order %s", order)
        scraped_auth = await self.get_auth()
        init_data_order = await self._init_data_order(order)
        delivery_info = await self._delivery_info(order, scraped_auth, init_data_order)
        return delivery_info

    async def _init_data_order(self, order: Order):
        async with self.client.get(
            "/remote/new_delivery/meest_express/init_data_order",
            params={
                "order_id": order.id,
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
        init_data_order: dict,
    ):
        order_data = init_data_order["orderData"]
        delivery_options = order_data["delivery_options"]

        try:
            request = {
                "is_another_recipient": None,
                "payer": 1,
                "COD": 0,

                "order_id": order.id,
                "delivery_option_id": str(order.delivery_option.id),

                "from_first_name": order_data["firstName"],
                "from_last_name": order_data["lastName"],
                "from_second_name": "",
                "phone": order_data["phone"],

                "city_ref": order_data["cityRef"],
                "city_name": order_data["cityName"],
                "city_doc_id": order_data["cityDocId"],

                "delivery_type": init_data_order["deliveryType"],

                "branch_ref": order_data["branchRef"],
                "branch_name": order_data["branchName"],
                "warehouse_doc_id": order_data["warehouseDocId"],

                "places": order_data["places"],

                "sending_place": delivery_options[0]["value"]
            }

        except KeyError as exc:
            raise GeneratingDeclarationException from exc

        async with self.client.post(
            "/remote/new_delivery/meest_express/generate_declaration",
            headers=self.post_headers(
                order_id=order.id,
                owner_id=scraped_auth["id"],
            ),
            json=request,
        ) as resp:
            if resp.content_type == "text/html":
                logger.error("Cookies are outdated. Clearing cookies and raising an exception.")
                self.client.cookie_jar.clear()
                raise OutdatedCookiesError
            return await resp.json()
