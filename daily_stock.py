"""Daily 08:50 report: everything ordered in the last 24 hours, against stock.

Every position ordered in the window appears, whether or not it is short —
the shortfall is a flag, not a filter, so a quiet day still produces a
report the owner can trust rather than an empty one he cannot tell from a
broken job.

Both outputs are off unless ``--apply`` is passed: the run prints the table
and the exact email body instead. That keeps a development run from
reaching a real inbox.
"""

import argparse
import asyncio
import datetime
import io
import logging
import os
from dataclasses import dataclass

import google.auth
import gspread
from dotenv import load_dotenv
from google.cloud import secretmanager_v1

from src.clock import KYIV, daily_window, now_kyiv
from src.mail.sender import MailSender
from src.models.product import Product
from src.prom.client import PromAPIClient
from src.stock.stock_manager import StockManager

logger = logging.getLogger(__name__)

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

SPREADSHEET = "Склад Intertool"
STOCK_WORKSHEET = "Товари"
DEFAULT_RECIPIENT = "willitools@gmail.com"

#: The owner asked for ALL orders in the window, cancellations included.
#: Put e.g. "cancelled" here to drop them; nothing else needs to change.
EXCLUDED_ORDER_STATUSES: tuple[str, ...] = ()

#: The API window is only a prefilter. Prom's date_from/date_to are
#: documented without an offset, so how the server reads them is not
#: guaranteed; we ask for a day either side and cut the exact boundary
#: ourselves on the aware timestamps Prom returns.
WINDOW_MARGIN = datetime.timedelta(days=1)

HEADER = [
    "Артикул",
    "Товар",
    "Замовлено",
    "На складі",
    "Вистачає",
    "Замовлень",
]

IN_STOCK = "Так"
NOT_ENOUGH = "Ні"
UNKNOWN = "Немає в таблиці"

#: Product names run past 100 characters; the mail is read in a monospace
#: column, so they are trimmed there. The worksheet keeps them in full.
MAX_NAME_WIDTH = 58


def format_quantity(value: float | int) -> str:
    """Prom sends quantities as floats; 1.0 should not read as "1.0"."""
    return str(int(value)) if float(value).is_integer() else str(value)


def normalize_sku(sku: str | None) -> str | None:
    """SKUs arrive from hand-touched sources; whitespace must not break
    matching (the stock sheet had entries like "TC-7635\\n\\n")."""
    return sku.strip() if sku else sku


@dataclass(frozen=True)
class ReportRow:
    sku: str
    name: str
    ordered: float
    in_stock: int | None
    orders: int

    @property
    def status(self) -> str:
        if self.in_stock is None:
            return UNKNOWN
        return IN_STOCK if self.in_stock >= self.ordered else NOT_ENOUGH

    def as_row(self, name_width: int | None = None) -> list:
        name = self.name
        if name_width and len(name) > name_width:
            name = name[: name_width - 1] + "…"
        return [
            self.sku,
            name,
            format_quantity(self.ordered),
            "—" if self.in_stock is None else self.in_stock,
            self.status,
            self.orders,
        ]


def orders_in_window(orders, start, end):
    """Orders created within ``[start, end)``, boundary cut on aware times."""
    selected = []
    for order in orders:
        created = order.datetime_created
        if created is None or not (start <= created < end):
            continue
        if order.status and order.status.name in EXCLUDED_ORDER_STATUSES:
            continue
        selected.append(order)
    return selected


def build_report(orders, stock_products: list[Product]) -> list[ReportRow]:
    """Fold orders into one row per SKU, priced against the stock sheet.

    Pure: no Prom, no Google. Ordering is shortfalls first, then by
    quantity ordered, so the rows that need action are at the top.
    """
    stock = {
        normalize_sku(product.sku): product.quantity_in_stock
        for product in stock_products
        if normalize_sku(product.sku)
    }

    ordered: dict[str, float] = {}
    names: dict[str, str] = {}
    order_counts: dict[str, set] = {}

    for order in orders:
        for line in order.products or []:
            sku = normalize_sku(line.sku)
            if not sku:
                continue
            ordered[sku] = ordered.get(sku, 0) + (line.quantity or 0)
            names.setdefault(sku, line.name or "")
            order_counts.setdefault(sku, set()).add(order.id)

    rows = [
        ReportRow(
            sku=sku,
            name=names.get(sku, ""),
            ordered=quantity,
            in_stock=stock.get(sku),
            orders=len(order_counts.get(sku, ())),
        )
        for sku, quantity in ordered.items()
    ]

    rank = {NOT_ENOUGH: 0, UNKNOWN: 1, IN_STOCK: 2}
    rows.sort(key=lambda row: (rank[row.status], -row.ordered, row.sku))
    return rows


def render_email(rows: list[ReportRow], start, end) -> tuple[str, str]:
    """Return the (subject, body) of the report mail."""
    short = [row for row in rows if row.status != IN_STOCK]
    window = (
        f"{start.strftime('%d.%m.%Y %H:%M')} — {end.strftime('%d.%m.%Y %H:%M')}"
    )
    subject = (
        f"Замовлення за добу {end.strftime('%d.%m.%Y')}: "
        f"{len(rows)} позицій, {len(short)} під питанням"
    )

    cells = [row.as_row(MAX_NAME_WIDTH) for row in rows]
    widths = [
        max([len(HEADER[i])] + [len(str(cell[i])) for cell in cells])
        for i in range(len(HEADER))
    ]

    def line(cells):
        return "  ".join(
            str(cell).ljust(widths[i]) for i, cell in enumerate(cells)
        ).rstrip()

    body = [
        f"Період: {window} (Київ)",
        f"Позицій: {len(rows)}. Потребують уваги: {len(short)}.",
        "",
        line(HEADER),
        line(["-" * width for width in widths]),
    ]
    body += [line(cell) for cell in cells]
    if not rows:
        body.append("За цей період замовлень не було.")

    return subject, "\n".join(body)


async def collect_rows(prom_client, stock_manager, start, end):
    orders = await prom_client.get_orders(
        date_from=(start - WINDOW_MARGIN).strftime("%Y-%m-%dT%H:%M:%S"),
        date_to=(end + WINDOW_MARGIN).strftime("%Y-%m-%dT%H:%M:%S"),
        paginate=True,
    )
    selected = orders_in_window(orders, start, end)
    logger.info("%s orders fetched, %s inside the window", len(orders), len(selected))
    return build_report(selected, stock_manager.get_products())


async def main(args):
    start, end = daily_window(args.now or now_kyiv())
    logger.info("Window %s -> %s", start.isoformat(), end.isoformat())

    creds, _ = google.auth.default(scopes=scope)
    gspread_client = gspread.client.Client(creds)

    stock_manager = StockManager(
        client=gspread_client,
        spreadsheet=SPREADSHEET,
        worksheet=STOCK_WORKSHEET,
    )

    prom_client = PromAPIClient(args.prom_token)
    rows = await collect_rows(prom_client, stock_manager, start, end)

    subject, body = render_email(rows, start, end)
    title = end.strftime("%Y-%m-%d %H-%M") + " Замовлення-склад"

    if not args.apply:
        print(f"[dry-run] worksheet: {title}")
        print(f"[dry-run] to: {args.to}")
        print(f"[dry-run] subject: {subject}")
        print(body)
        return

    stock_manager.create_report(title, HEADER, [row.as_row() for row in rows])
    sender = MailSender.from_env()
    sender.send(sender.build(args.to, subject, body))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

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

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prom-token", help="Prom API token", default=os.getenv("PROM_TOKEN")
    )
    parser.add_argument(
        "--to",
        help="Report recipient",
        default=os.getenv("REPORT_EMAIL_TO", DEFAULT_RECIPIENT),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the worksheet and send the email; otherwise print both",
    )
    parser.add_argument(
        "--now",
        type=lambda value: datetime.datetime.fromisoformat(value).replace(tzinfo=KYIV),
        help="Anchor the window at this Kyiv time instead of now",
    )

    asyncio.run(main(parser.parse_args()))
