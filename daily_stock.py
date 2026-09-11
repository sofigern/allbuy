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
import openpyxl
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

    def as_row(self) -> list:
        return [
            self.sku,
            self.name,
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
    """Return the (subject, body) of the report mail.

    The full table travels as the .xlsx attachment (see ``build_workbook``);
    a phone notification shows this body, not the attachment, so it has to
    stand on its own: window, how many SKUs, how many are short.
    """
    short = [row for row in rows if row.status != IN_STOCK]
    window = (
        f"{start.strftime('%d.%m.%Y %H:%M')} — {end.strftime('%d.%m.%Y %H:%M')}"
    )
    subject = (
        f"Замовлення за добу {end.strftime('%d.%m.%Y')}: "
        f"{len(rows)} позицій, {len(short)} під питанням"
    )

    body = [
        f"Період: {window} (Київ)",
        f"Позицій: {len(rows)}. Потребують уваги: {len(short)}.",
    ]
    if rows:
        body.append("Повний список — у прикріпленому файлі.")
    else:
        body.append("За цей період замовлень не було.")

    return subject, "\n".join(body)


def build_workbook(rows: list[ReportRow]) -> bytes:
    """The report as an .xlsx attachment: same header and rows as the tab
    ``StockManager.create_report`` writes, untruncated names included."""
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(HEADER)
    for row in rows:
        sheet.append(row.as_row())

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


async def collect_rows(prom_client, stock_manager, start, end):
    orders = await prom_client.get_orders(
        date_from=(start - WINDOW_MARGIN).strftime("%Y-%m-%dT%H:%M:%S"),
        date_to=(end + WINDOW_MARGIN).strftime("%Y-%m-%dT%H:%M:%S"),
        paginate=True,
    )
    selected = orders_in_window(orders, start, end)
    logger.info("%s orders fetched, %s inside the window", len(orders), len(selected))
    return build_report(selected, stock_manager.get_products())


def deliver_report(stock_manager, sender, title, header, rows, to, subject, body, attachment):
    """Write the worksheet tab, then send the report email regardless.

    The worksheet write is best-effort: on failure it is logged, not
    raised, so a broken sheet write (a rerun hitting a duplicate title, a
    Sheets outage) does not also swallow the email - the run would
    otherwise fail before the email is even built, leaving the owner with
    neither a tab nor a mail and no idea why.
    """
    try:
        stock_manager.write_report(title, header, rows)
    except Exception:
        logger.exception(
            "Failed to write report worksheet %r; sending the email anyway", title
        )

    sender.send(sender.build(to, subject, body, attachment=attachment))


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
    attachment_name = f"{title}.xlsx"

    if not args.apply:
        print(f"[dry-run] worksheet: {title}")
        print(f"[dry-run] to: {args.to}")
        print(f"[dry-run] subject: {subject}")
        print(f"[dry-run] attachment: {attachment_name}")
        print(body)
        return

    deliver_report(
        stock_manager,
        MailSender.from_env(),
        title,
        HEADER,
        [row.as_row() for row in rows],
        args.to,
        subject,
        body,
        (attachment_name, build_workbook(rows)),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    secret_client = secretmanager_v1.SecretManagerServiceClient()
    _, project_id = google.auth.default()
    response = secret_client.access_secret_version(
        name=f"projects/{project_id}/secrets/ALLBUYBOTCONF/versions/latest"
    )
    payload = response.payload.data.decode("UTF-8")
    load_dotenv(stream=io.StringIO(payload))

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
