import gspread

from src.models.product import Product


class StockManager:
    SKU_COLUMN = "Артикул"
    NAME_COLUMN = "Товар"
    QUANTITY_COLUMN = "Кількість"
    PRICE_COLUMN = "Ціна"

    def __init__(
        self,
        client: gspread.client.Client,
        spreadsheet: str,
        worksheet: str,
    ):
        self.gc = client
        self.spreadsheet = self.gc.open(spreadsheet)
        try:
            self.worksheet = self.spreadsheet.worksheet(worksheet)
        except gspread.exceptions.WorksheetNotFound:
            titles = [ws.title for ws in self.spreadsheet.worksheets()]
            raise ValueError(
                f"Worksheet {worksheet!r} not found in spreadsheet "
                f"{spreadsheet!r}; available worksheets: {titles}"
            ) from None

    def get_products(self) -> list[Product]:
        return self.parse_rows(self.worksheet.get_all_values())

    def create_report(
        self,
        title: str,
        header: list[str],
        rows: list[list],
        index: int = 1,
    ) -> None:
        """Write ``rows`` to a brand new worksheet named ``title``."""
        worksheet = self.spreadsheet.add_worksheet(
            title, rows=max(len(rows) + 1, 1), cols=len(header), index=index
        )
        worksheet.append_row(header)
        if rows:
            worksheet.append_rows(rows)

    def replace_report(
        self,
        title: str,
        header: list[str],
        rows: list[list],
    ) -> None:
        """Overwrite an existing worksheet named ``title`` in place."""
        worksheet = self.spreadsheet.worksheet(title)
        worksheet.clear()
        worksheet.append_row(header)
        if rows:
            worksheet.append_rows(rows)

    def write_report(
        self,
        title: str,
        header: list[str],
        rows: list[list],
        index: int = 1,
    ) -> None:
        """Create the ``title`` tab, or replace it if one already exists.

        A daily job names its tab after the report window, so a rerun (or a
        scheduler retry) reuses the exact same title; ``create_report``'s
        ``add_worksheet`` rejects a duplicate outright, which must not turn
        into a silent no-op for the whole run.
        """
        titles = {worksheet.title for worksheet in self.spreadsheet.worksheets()}
        if title in titles:
            self.replace_report(title, header, rows)
        else:
            self.create_report(title, header, rows, index=index)

    @classmethod
    def parse_rows(cls, data: list[list[str]]) -> list[Product]:
        if not data:
            return []

        header = [cell.strip() for cell in data[0]]
        required = (
            cls.SKU_COLUMN, cls.NAME_COLUMN, cls.QUANTITY_COLUMN, cls.PRICE_COLUMN
        )
        missing = [column for column in required if column not in header]
        if missing:
            raise ValueError(
                f"Stock worksheet is missing required columns {missing}; "
                f"header row: {header}"
            )

        sku_col = header.index(cls.SKU_COLUMN)
        name_col = header.index(cls.NAME_COLUMN)
        quantity_col = header.index(cls.QUANTITY_COLUMN)
        price_col = header.index(cls.PRICE_COLUMN)

        products = []
        for row in data[1:]:
            # Cells are hand-edited and often carry stray newlines/spaces
            # (e.g. "TC-7635\n\n"), which must not break SKU matching.
            sku = row[sku_col].strip()
            if not sku:
                continue
            products.append(
                Product(
                    sku=sku,
                    name=row[name_col].strip(),
                    quantity_in_stock=int(row[quantity_col].strip() or 0),
                    price=float(row[price_col].replace(",", ".").strip() or 0),
                )
            )

        return products
