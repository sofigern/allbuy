import gspread

from src.models.product import Product


class StockManager:
    def __init__(
        self,
        client: gspread.client.Client,
        spreadsheet: str,
        worksheet: str,
    ):
        self.gc = client
        self.spreadsheet = self.gc.open(spreadsheet)
        self.worksheet = self.spreadsheet.worksheet(worksheet)

    def get_products(self) -> list[Product]:
        products = []
        data = self.worksheet.get_all_values()
        if data:
            products = [
                Product(
                    sku=row[0],
                    name=row[1],
                    quantity_in_stock=int(row[2]),
                    price=float(row[6].replace(",", ".")),
                )
                for row in data[1:]
            ]

        return products
