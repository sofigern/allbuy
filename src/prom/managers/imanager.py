from src.models.order import Order

from src.prom.client import PromAPIClient
from src.prom.remote.base import BaseScraperClient


class IManager:

    def __init__(
        self,
        api_client: PromAPIClient,
        scrape_client: BaseScraperClient | None = None,
    ):
        raise NotImplementedError

    async def process_order(
        self,
        order: Order,
        initial: bool = False,
    ) -> Order:
        """Process order."""
        raise NotImplementedError
