import argparse
import asyncio
import datetime
import io
import os
from dataclasses import replace

import google.auth
import gspread
from dotenv import load_dotenv
from google.cloud import secretmanager_v1

from src.prom.client import PromAPIClient
from src.stock.intertool_manager import IntertoolManager
from src.stock.stock_manager import StockManager

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]


def normalize_sku(sku: str | None) -> str | None:
    """SKUs arrive from three hand-touched sources; whitespace must not
    break matching (the stock sheet had entries like "TC-7635\\n\\n")."""
    return sku.strip() if sku else sku


def plan_updates(prom_products, stock_products, intertool_products):
    """Decide presence for every prom product.

    A product counts as available iff its quantity on the owner's stock
    sheet is > 0 OR the intertool feed marks it available — the sheet is
    authoritative for items intertool has delisted from its b2c feed.

    Returns (update_products, unknown_products) where update_products is
    a list of (old_product, new_product) pairs.
    """
    i_products = {normalize_sku(p.sku): p for p in intertool_products}

    known_skus = {normalize_sku(p.sku) for p in stock_products}
    known_skus |= {normalize_sku(p.sku) for p in intertool_products}

    available_skus = {
        normalize_sku(p.sku) for p in stock_products if p.quantity_in_stock > 0
    }
    available_skus |= {
        normalize_sku(p.sku) for p in intertool_products if p.in_stock
    }

    update_products = []
    unknown_products = []

    for prom_product in prom_products:
        product = prom_product
        sku = normalize_sku(product.sku)

        if sku not in known_skus:
            unknown_products.append(product)
            continue

        if intertool_product := i_products.get(sku):
            # Kept as-is pending the owner's answer on whether the prom
            # price should be raised to a higher intertool price.
            if intertool_product.price >= product.price:
                product = replace(product, price=intertool_product.price)

        if sku in available_skus:
            if product.presence == "not_available":
                product = replace(product, presence="available", in_stock=True)
        else:
            if product.presence == "available":
                product = replace(product, presence="not_available", in_stock=False)

        if product is not prom_product:
            if not (product.presence == prom_product.presence == "not_available"):
                update_products.append((prom_product, product))

    return update_products, unknown_products


async def main(args):
    creds, project_id = google.auth.default(scopes=scope)
    gspread_client = gspread.client.Client(creds)

    prom_client = PromAPIClient(args.prom_token)
    prom_products = await prom_client.get_products()

    stock_manager = StockManager(
        client=gspread_client,
        spreadsheet="Склад Intertool",
        worksheet="Товари",
    )
    stock_products = stock_manager.get_products()

    intertool_manager = IntertoolManager()
    intertool_products = intertool_manager.get_products(from_file=False)

    update_products, unknown_products = plan_updates(
        prom_products, stock_products, intertool_products
    )

    spreadsheet = gspread_client.open("Склад Intertool")

    if update_products:
        worksheet_name = (
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " Оновлення"
        )

        updated = spreadsheet.add_worksheet(worksheet_name, rows=1, cols=8, index=1)
        updated.append_row(
            [
                "ID",
                "SKU",
                "Назва",
                "Ціна Пром",
                "Ціна Інтертул",
                "Попередній Статус",
                "Новий Статус",
                "Посилання",
            ]
        )

        res = []
        for old_product, new_product in update_products:
            res.append(
                [
                    old_product.id,
                    old_product.sku,
                    old_product.name,
                    old_product.price,
                    new_product.price,
                    "Готово до відправлення"
                    if old_product.presence == "available"
                    else "Немає в наявності",
                    "Готово до відправлення"
                    if new_product.presence == "available"
                    else "Немає в наявності",
                    old_product.url,
                ]
            )
        updated.append_rows(res)
        # await prom_client.edit_products([p for (_, p) in update_products])

    unknown = spreadsheet.worksheet("Невідомі")
    unknown.clear()
    unknown.append_row(["ID", "SKU", "Назва", "Ціна Пром", "Статус", "Посилання"])
    res = []
    for product in unknown_products:
        res.append(
            [
                product.id,
                product.sku,
                product.name,
                product.price,
                "Готово до відправлення"
                if product.presence == "available"
                else "Немає в наявності",
                product.url,
            ]
        )
    unknown.append_rows(res)


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

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--prom-token", help="Prom API token", default=os.getenv("PROM_TOKEN")
    )

    args = parser.parse_args()
    asyncio.run(main(args))
