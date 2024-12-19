import logging

from src.models.order import Order
from src.prom.exceptions import OutdatedCookiesError, GeneratingDeclarationException
from src.prom.remote.base import BaseScraperClient


logger = logging.getLogger(__name__)


class NovaPoshtaScraperClient(BaseScraperClient):
   
    async def generate_declaration(self, order: Order) -> dict:
        logger.info("Generating declaration for order %s", order)
        scraped_order = await self.get_order(order)
        init_data_order = await self._init_data_order(scraped_order)
        delivery_info = await self._delivery_info(scraped_order, init_data_order)
        return delivery_info

    async def _init_data_order(
        self,
        scraped_order: dict,
    ):
        async with self.client.get(
            "/remote/delivery/nova_poshta/init_data_order",
            params={
                "order_id": scraped_order["id"],
                "delivery_option_id": scraped_order["delivery_option_raw_id"],
                "is_np_pochtomat": "true",
                "cart_total_price": scraped_order["cartTotalPriceInDefaultCurrency"],
            }
        ) as resp:
            if resp.content_type == "text/html":
                logger.error("Cookies are outdated. Clearing cookies and raising an exception.")
                self.client.cookie_jar.clear()
                raise OutdatedCookiesError
            return (await resp.json())["data"]
    
    async def _delivery_info(
        self,
        scraped_order: dict,
        init_data_order
    ):
        default_price = scraped_order["cartTotalPriceInDefaultCurrency"]
        default_payer = init_data_order["payerType"]
        try:
            request = {
                "addition_info": "",
                "is_another_recipient": None,

                "delivery_option_id": scraped_order["delivery_option_raw_id"],
                "order_id": scraped_order["id"],

                "warehouse_name": init_data_order["warehouseName"],
                "warehouse_doc_id": init_data_order["warehouseDocId"],
                "warehouse_ref": init_data_order["warehouse"],

                "city_doc_id": init_data_order["cityDocId"],
                "city_ref": init_data_order["city"],
                "city_name": init_data_order["cityName"],

                "service_type": init_data_order["serviceType"],
                "np_payer_type": init_data_order["payerType"],

                "from_first_name": init_data_order["firstName"],
                "from_last_name": init_data_order["lastName"],
                "from_second_name": "",
                "phone": init_data_order["phone"],
                
                "description": init_data_order["description"],
                "sender_warehouse_ref": init_data_order["warehouseFrom"],
                "box_items": init_data_order["boxItems"],

                "is_redelivery_set": init_data_order["isRedelivery"],
                "redelivery_amount": init_data_order.get("redeliveryAmount", default_price),
                "redelivery_payment_type": "cash",
                "redelivery_payer_type": init_data_order.get("redeliveryPayerType", default_payer),

                "document_weight": init_data_order.get("documentWeight", "0.1"),
                "cargo_type": init_data_order.get("cargoType", "Cargo"),

                "order_cost": init_data_order.get("packageCost", default_price),
                "cod_amount": init_data_order.get("cod_amount", str(default_price)),
                "cod_payer_type": init_data_order.get("cod_payer_type", default_payer.lower()),

                "send_date": init_data_order.get("sendDate", init_data_order["dateModified"]),
            }
        except KeyError as exc:
            raise GeneratingDeclarationException from exc
        
        if declaration_id := init_data_order.get("declarationId"):
            request["declaration_id"] = declaration_id
        
        if was_printed := init_data_order.get("wasPrinted"):
            request["was_printed"] = was_printed

        async with self.client.post(
            "/market/application/nova_poshta/delivery_info",
            headers=self.post_headers(
                order_id=scraped_order["delivery_option_raw_id"], 
                owner_id=init_data_order["ownerId"],
            ),
            json=request,
        ) as resp:
            if resp.content_type == "text/html":
                logger.error("Cookies are outdated. Clearing cookies and raising an exception.")
                self.client.cookie_jar.clear()
                raise OutdatedCookiesError
            return (await resp.json())
