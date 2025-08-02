import argparse
import asyncio
from dataclasses import replace
import datetime
import io
import os

from dotenv import load_dotenv
import google.auth
from google.cloud import secretmanager_v1
import gspread

from src.prom.client import PromAPIClient
from src.stock.stock_manager import StockManager
from src.stock.intertool_manager import IntertoolManager


scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]


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
    i_products = {p.sku: p for p in intertool_products}
    
    available_on_stock = [p.sku for p in stock_products if p.quantity_in_stock > 0]
    not_available_on_stock = [p.sku for p in stock_products if p.quantity_in_stock == 0]

    available_on_intertool = [p.sku for p in intertool_products if p.in_stock]
    not_available_on_intertool = [p.sku for p in intertool_products if not p.in_stock]
    
    update_products = []
    unknown_products = []
    
    for prom_product in prom_products:
        product = prom_product

        if product.sku not in (
            available_on_intertool +
            not_available_on_intertool +
            available_on_stock +
            not_available_on_stock
        ):
            unknown_products.append(product)
            continue
        
        if (intertool_product := i_products.get(prom_product.sku)):
            if intertool_product.price != product.price:
                product = replace(product, price=intertool_product.price)

        if (product.sku in (available_on_stock + available_on_intertool)):
            if product.presence == "not_available":
                product = replace(product, presence="available", in_stock=True)
        else:
            if product.presence == "available":
                product = replace(product, presence="not_available", in_stock=False)
        
        if product is not prom_product:
            if not (product.presence == prom_product.presence == "not_available"):
                update_products.append((prom_product, product))

    spreadsheet = gspread_client.open("Склад Intertool")

    if update_products:
        worksheet_name = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " Оновлення"

        updated = spreadsheet.add_worksheet(worksheet_name, rows=1, cols=8, index=1)
        updated.append_row(["ID", "SKU", "Назва", "Ціна Пром", "Ціна Інтертул", "Попередній Статус", "Новий Статус", "Посилання"])
        
        res = []
        for old_product, new_product in update_products:
            res.append([
                old_product.id,
                old_product.sku,
                old_product.name,
                old_product.price,
                new_product.price,
                "Готово до відправлення" if old_product.presence == "available" else "Немає в наявності",
                "Готово до відправлення" if new_product.presence == "available" else "Немає в наявності",
                old_product.url,
            ])
        updated.append_rows(res)
        # await prom_client.edit_products([p for (_, p) in update_products])
    
    unknown = spreadsheet.worksheet("Невідомі")
    unknown.clear()
    unknown.append_row(["ID", "SKU", "Назва", "Ціна Пром", "Статус", "Посилання"])
    res = []
    for product in unknown_products:
        res.append([
            product.id,
            product.sku,
            product.name,
            product.price,
            "Готово до відправлення" if product.presence == "available" else "Немає в наявності",
            product.url,
        ])
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
        "--prom-token", help="Prom API token",
        default=os.getenv("PROM_TOKEN")
    )

    args = parser.parse_args()
    asyncio.run(main(args))
