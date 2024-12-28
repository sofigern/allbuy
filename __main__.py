import argparse
import asyncio
import logging

import io
import os
import urllib

from dotenv import load_dotenv
from flatdict import FlatDict

import gspread
import google.auth
from google.cloud import run_v2, secretmanager_v1, firestore
# from oauth2client.service_account import ServiceAccountCredentials

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

def read_orders(client: gspread.client.Client, name: str) -> dict:
    sheet = client.open("AllBuy Storage").worksheet(name)

    data = sheet.get_all_values()
    result = {}

    # Convert to JSON format
    if data:
        headers = data[0]  # First row as headers
        rows = data[1:]    # Remaining rows as data

        # Create a list of dictionaries
        result = {row[0]: dict(zip(headers, row)) for row in rows}
    return result


def write_orders(client: gspread.client.Client, name: str, orders: dict):
    sheet = client.open("AllBuy Storage").worksheet(name)

    headers = set()
    for order in orders.values():
        headers.update(order.keys())
    headers = ["id"] + sorted([h for h in headers if h != "id"])

    for h in headers:
        is_empty_field = True
        for order in orders.values():
            val = order.get(h)
            if not isinstance(val, FlatDict) and (val is not None) and (val != ""):
                is_empty_field = False
                break
        if is_empty_field:
            headers.remove(h)

    res = []

    for order in orders.values():
        row = []
        for h in headers:
            try:
                val = order.get(h)
            except TypeError:
                val = None
            else:
                if isinstance(val, FlatDict):
                    val = None
            finally:
                row.append(val)
        res.append(row)

    sheet.clear()
    sheet.append_row(headers)
    sheet.append_rows(res)

# Define the scope
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]


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

    parser.add_argument(
        "--signal-disallowed", help="Signal disallowed phone number",
        action="store_true"
    )

    parser.add_argument(
        "--order-id", help="Order ID",
        action="append"
    )

    parser.add_argument(
        "--force", help="Force refresh",
        action="store_true"
    )

    parser.add_argument(
        "--admin-phone", help="Admin phone number",
        default=os.getenv("ADMIN_PHONE")
    )

    # Parse the arguments
    args = parser.parse_args()

    # Convert to a dictionary
    return args


async def main():
    parsed_data = parse_arguments()
    creds, project_id = google.auth.default(scopes=scope)

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

    signal_bot = None
    if not parsed_data.signal_disallowed:
        if not parsed_data.signal_phone or not parsed_data.signal_group:
            raise ValueError("Signal Phone number and group ID are required.")

        signal_bot = SignalBot(**{
            "signal_service": signal_service,
            "phone_number": parsed_data.signal_phone,
            "group_id": parsed_data.signal_group,
            "force": parsed_data.force
        })

    prom_client = PromAPIClient(
        parsed_data.prom_token,
    )

    # db = firestore.Client(database="all-buy-firestore")

    # paid_orders = {
    #     doc.id: doc.to_dict()
    #     for doc in db.collection("paid_orders").stream()
    #     if doc
    # }

    # pending_orders = {
    #     doc.id: doc.to_dict()
    #     for doc in db.collection("pending_orders").stream()
    #     if doc
    # }

    gspread_client = gspread.client.Client(creds)

    paid_orders = read_orders(gspread_client, "Paid")
    pending_orders = read_orders(gspread_client, "Pending")

    allbuy_bot = AllBuyBot(
        client=prom_client,
        messenger=signal_bot,
        cookies=get_cookies(),
        paid_orders=paid_orders,
        pending_orders=pending_orders,
        admin_phone=parsed_data.admin_phone,
    )

    try:
        await allbuy_bot.refresh_shop(orders=parsed_data.order_id)
    except OutdatedCookiesError:
        if signal_bot:
            await signal_bot.send(
                "Авторизаційні дані застаріли. Потрібно оновити Cookies.",
                "Наразі опрацювання нових замовлень неможливе."
            )
    else:
        if not parsed_data.order_id:
            write_orders(gspread_client, "Paid", allbuy_bot.paid_orders)
            write_orders(gspread_client, "Pending", allbuy_bot.pending_orders)

            # for doc in db.collection("paid_orders").stream():
            #     if doc.id not in allbuy_bot.paid_orders:
            #         logger.info("%s was processed and removed from the database", doc.id)
            #         doc.reference.delete()

            # for order, data in allbuy_bot.paid_orders.items():
            #     db.collection("paid_orders").document(order).set(data)

            # for doc in db.collection("pending_orders").stream():
            #     if doc.id not in allbuy_bot.pending_orders:
            #         logger.info("%s was processed and removed from the database", doc.id)
            #         doc.reference.delete()

            # for order, data in allbuy_bot.pending_orders.items():
            #     db.collection("pending_orders").document(order).set(data)


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
        load_dotenv("local.env", override=True)

    asyncio.run(main())
