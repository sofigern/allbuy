from src.models.order import Order
from src.models.delivery_provider import DeliveryProviders

from src.exceptions import DeliveryProviderNotAllowedError
from src.prom.client import PromAPIClient
from src.prom.remote.nova_poshta import NovaPoshtaScraperClient
from src.prom.remote.rozetka import RozetkaScraperClient
from src.prom.remote.ukr_poshta import UkrPoshtaScraperClient
from src.prom.managers.imanager import IManager
from src.prom.managers.dummy import DummyManager
from src.prom.managers.nova_poshta import NovaPoshtaManager
from src.prom.managers.pickup import PickupManager
from src.prom.managers.rozetka import RozetkaManager
from src.prom.managers.ukr_poshta import UkrPoshtaManager
from src.signal.bot import SignalBot


class Director:
    def __init__(
        self,
        api_client: PromAPIClient,
        messenger: SignalBot | None = None,
        cookies: str | None = None,
    ) -> None:
        self.api_client = api_client
        self.cookies = cookies
        self.messenger = messenger
        self.scrapers = {}
        self.managers = {}

    def assign(self, order: Order) -> IManager:

        if order.delivery_option not in self.managers:
            manager = None
            if order.delivery_option == DeliveryProviders.PICKUP.value:
                manager = PickupManager(
                    api_client=self.api_client,
                    messenger=self.messenger,
                )
            elif order.delivery_option == DeliveryProviders.NOVA_POSHTA.value:
                scraper_client = NovaPoshtaScraperClient(cookies=self.cookies)
                manager = NovaPoshtaManager(
                    api_client=self.api_client,
                    scrape_client=scraper_client,
                    messenger=self.messenger,
                )
            elif order.delivery_option == DeliveryProviders.UKR_POSHTA.value:
                scraper_client = UkrPoshtaScraperClient(cookies=self.cookies)
                manager = UkrPoshtaManager(
                    api_client=self.api_client,
                    scrape_client=scraper_client,
                    messenger=self.messenger,
                )
            elif order.delivery_option == DeliveryProviders.ROZETKA.value:
                scraper_client = RozetkaScraperClient(cookies=self.cookies)
                manager = RozetkaManager(
                    api_client=self.api_client,
                    scrape_client=scraper_client,
                    messenger=self.messenger,
                )
            else:
                manager = DummyManager(
                    api_client=self.api_client,
                    messenger=self.messenger,
                )

            self.managers[order.delivery_option] = manager

        if self.managers[order.delivery_option] is None:
            raise DeliveryProviderNotAllowedError(order)

        return self.managers[order.delivery_option]
