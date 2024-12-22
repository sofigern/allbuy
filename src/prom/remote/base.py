import base64
import logging

import aiohttp

from src.prom.exceptions import OutdatedCookiesError
from src.prom.utils import prepare_cookies, dict_from_cookiejar
from src.models.order import Order


logger = logging.getLogger(__name__)


class BaseScraperClient:
    def __init__(
        self,
        cookies: str | None = None,
        base_url: str = "https://my.prom.ua/",
    ):
        self.base_url = base_url
        self.cookies = cookies

        if self.cookies:
            cookies = {}
            cookies_str = base64.b64decode(self.cookies).decode("utf-8")
            self.cookies = prepare_cookies(cookies_str)

        self.client = aiohttp.ClientSession(
            base_url=self.base_url,
            headers={
                "Content-Type": "application/json",
            },
            cookies=self.cookies,
        )

    @classmethod
    def order_url(cls, order_id: int):
        return f"https://my.prom.ua/cms/order/edit/{order_id}"

    def post_headers(self, order_id: int, owner_id: int) -> dict:
        cookies = dict_from_cookiejar(self.client.cookie_jar)
        return {
            "origin": "https://my.prom.ua",
            "priority": "u=1, i",
            "referer": self.order_url(order_id),
            "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            # pylint: disable=C0301
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",   # noqa: E501
            # pylint: enable=C0301
            "x-csrftoken": cookies["csrf_token"],
            "x-promuserid": str(owner_id),
            "x-requested-with": "XMLHttpRequest",
        }

    async def get_order(
        self,
        order: Order,
    ) -> dict:
        async with self.client.get(
            "remote/order_api/get_order",
            params={
                "id": order.id,
                "sorted_products": 0,
            },
        ) as resp:
            if resp.content_type == "text/html":
                logger.error("Cookies are outdated. Clearing cookies and raising an exception.")
                self.client.cookie_jar.clear()
                raise OutdatedCookiesError
            return (await resp.json())["order"]

    async def get_auth(self) -> dict:
        async with self.client.get(
            "/remote/auth/info",
        ) as resp:
            if resp.content_type == "text/html":
                logger.error("Cookies are outdated. Clearing cookies and raising an exception.")
                self.client.cookie_jar.clear()
                raise OutdatedCookiesError
            return await resp.json()

    async def generate_declaration(self, order: Order) -> dict:
        raise NotImplementedError
