from aiohttp import web

import argparse
import asyncio
import logging

import io
import os
import urllib

from dotenv import load_dotenv 

import google.auth
from google.cloud import run_v2, secretmanager_v1, firestore

from src.signal.bot import SignalBot
from src.prom.client import PromAPIClient

from src.allbuy_bot import AllBuyBot
from src.prom.exceptions import (
    OutdatedCookiesError,
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set the minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Log message format
    handlers=[
        logging.StreamHandler(),  # Output logs to console
        # You can also add a file handler if needed:
        # logging.FileHandler('app.log')  # Output logs to a file
    ]
)


def get_cookies():
    return os.getenv("COOKIES")

logger = logging.getLogger(__name__)


def parse_arguments():
    """
    Parse command-line arguments into a dictionary using argparse.
    :return: Parsed arguments as a dictionary
    """
    parser = argparse.ArgumentParser(description="Parse phone number and group ID.")

    # Define the expected arguments
    parser.add_argument(
        "--signal-phone", help="Phone number (e.g., +380661234567)",
        default=os.getenv("SIGNAL_PHONE")
    )
    parser.add_argument(
        "--signal-group", help="Group ID",
        default=os.getenv("SIGNAL_GROUP")
    )

    parser.add_argument(
        "--signal-api-cli", help="Signal API client name",
        default=os.getenv("SIGNAL_API_CLI")
    )

    parser.add_argument(
        "--signal-api-region", help="Signal API region",
        default=os.getenv("SIGNAL_API_REGION")
    )

    parser.add_argument(
        "--prom-token", help="Prom API token",
        default=os.getenv("PROM_TOKEN")
    )

    # Parse the arguments
    args = parser.parse_args()

    # Convert to a dictionary
    return args


async def main():
    parsed_data = parse_arguments()
    _, project_id = google.auth.default()
    g_service_client = run_v2.ServicesClient()
    service = g_service_client.get_service(
        name=g_service_client.service_path(
            project_id, 
            parsed_data.signal_api_region,
            parsed_data.signal_api_cli,
        )
    )
    service_url = service.urls[0]
    signal_service = urllib.parse.urlparse(service_url).netloc

    if not parsed_data.signal_phone or not parsed_data.signal_group:
        raise ValueError("Signal Phone number and group ID are required.")

    signal_bot = SignalBot(**{
        "signal_service": signal_service,
        "phone_number": parsed_data.signal_phone,
        "group_id": parsed_data.signal_group,
    })

    prom_client = PromAPIClient(
        parsed_data.prom_token,
    )

    db = firestore.Client(database="all-buy-firestore")
    processed_orders = {
        doc.id: doc.to_dict()
        for doc in db.collection("processed_orders").stream()
        if doc
    }

    allbuy_bot = AllBuyBot(
        client=prom_client,
        messenger=signal_bot,
        cookies=get_cookies(),
        processed_orders=processed_orders,
    )

    # refresh_is_possible = True    

    # while True:
        
        # if refresh_is_possible:
    try:
        await allbuy_bot.refresh_shop()
    except OutdatedCookiesError:
        # refresh_is_possible = False
        await signal_bot.send(
            "Авторизаційні дані застаріли. Потрібно оновити Cookies.",
            "Наразі опрацювання нових замовлень неможливе."
        )
        # else:
        #     logger.warning("Outdated cookies. Refresh is not possible.")

        # await asyncio.sleep(60)
    else:
        for doc in db.collection("processed_orders").stream():
            if doc.id not in allbuy_bot.processed_orders:
                logger.info("%s was processed and removed from the database", doc.id)
                doc.reference.delete()
            db.collection("processed_orders").document(doc.id).delete()
        for order, data in allbuy_bot.processed_orders.items():
            db.collection("processed_orders").document(order).set(data)

async def start():
    # Create the web application
    # app = web.Application()
    # app.router.add_get('/', handle)  # Define a route

    # Start the server on all interfaces (0.0.0.0) and port 8080
    # runner = web.AppRunner(app)
    # await runner.setup()

    # site = web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 8080)))
    # await site.start()
    
    # print(f"Server started at http://0.0.0.0:{os.getenv('PORT', 8080)}")

    # Run the main logic in the same event loop
    await main()

if __name__ == "__main__":

    params = {}
    if not os.path.exists("local.env"):
        secret_client = secretmanager_v1.SecretManagerServiceClient()
        _, project_id = google.auth.default()
        response = secret_client.access_secret_version(
            name=f"projects/{project_id}/secrets/ALLBUYBOTCONF/versions/latest"
        )
        payload = response.payload.data.decode("UTF-8")
        load_dotenv(stream=io.StringIO(payload))
    else:
        load_dotenv("local.env")
    
    asyncio.run(start())
