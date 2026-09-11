# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- Add durable project-specific notes here as they are discovered through real work.

## Leftovers job (`leftowers.py`)

- Availability rule: a prom product is available iff its quantity on the owner's Google Sheet "Склад Intertool" / worksheet "Товари" is > 0 OR intertool's b2c XML stock feed marks it `available="true"`.
  The sheet is authoritative for items intertool has delisted from b2c (they show `available="false"` in the feed while the owner still holds stock).
  The owner has NO intertool B2B dealer login; do not build a B2B-cabinet availability source.
- The sheet is hand-edited: SKU cells carry stray newlines/spaces (e.g. `"TC-7635\n\n"`; 342 of ~1040 rows at 2026-07-06).
  All SKU matching must go through `normalize_sku` (strip); unstripped matching once flipped in-stock products to "Немає в наявності".
- "Товари" layout is header-named, not positional: `Артикул` (SKU), `Товар` (name), `Кількість` (quantity), `Ціна` (price); `StockManager.parse_rows` resolves columns by header and fails loudly if one is missing.
- The intertool feed (`s3.intertool.ua/b2c/.../stock/xml_output.xml`, ~46 MB) carries no quantity, only the `available` attribute; all four public feed variants agree with it.
- The price-raise block in `plan_updates` (raise prom price to intertool's when intertool is >=) is of unconfirmed intent with the owner — do not change it without his answer.
- The job's only production write is the report worksheets ("… Оновлення", "Невідомі") in the same spreadsheet; `edit_products` (prom mutation) is intentionally commented out.
  For local validation, call the pure `plan_updates` instead of `main()` so nothing is written.
- Tests: `pytest` from the repo root (`pytest.ini` sets `pythonpath = .`).
  pytest is a dev-only tool — it is not in `requirements.txt` (runtime deps only) and must be installed separately.

## Daily orders-vs-stock job (`daily_stock.py`)

- Runs at 08:50 Kyiv and reports the window `[08:50 yesterday, 08:50 today)`.
  The boundary is half-open so consecutive runs never drop or double-count an order landing on it.
- Every SKU ordered in the window appears, whether short or not; `Вистачає` is a flag, not a filter.
  An empty day says so in words, so a silent breakage does not look like a quiet day.
- Three distinct states, and they must stay distinct: enough stock, not enough, and SKU absent from the sheet.
  Stock `0` is *not* the same as absent — `0` means the sheet knows the item and has none.
- **Timezones.** Prom's public API returns `date_created` with an offset; the seller cabinet renders the
  same instant as a naive Kyiv wall clock. `src/clock.to_kyiv` normalises both to aware Europe/Kyiv, and
  `Order.datetime_created` / `Order.age` go through it. Before this, `Order` stripped the offset and
  compared it against a local `datetime.now()`, so on a UTC container every age was ~3 h out.
  Never compare a Prom timestamp to a naive `now()`.
- `date_from` / `date_to` on `/orders/list` are documented without an offset, so how the server reads them
  is not guaranteed. The job asks for a day either side (`WINDOW_MARGIN`) and cuts the exact boundary
  itself on the aware timestamps Prom returns; the API window is only a prefilter. Requires
  `PromAPIClient.get_orders(paginate=True)`, which walks `last_id`.
- Volume, measured over the 365 days to 2026-09-11 (15 726 orders): an 08:50→08:50 window held a median
  of 44 orders and never more than 72, with 64 distinct SKUs at the median and 134 at the most. One
  100-order page covers it today, which is why paging exists rather than a larger limit.
- `EXCLUDED_ORDER_STATUSES` is empty: the owner asked for *all* orders in the window, cancellations
  included. Add `"cancelled"` there to change that; nothing else needs touching.
- **Both outputs are off unless `--apply` is passed.** Without it the run prints the worksheet title and
  the exact email body. The scheduled invocation must pass `--apply`.
- SMTP settings come from the same `ALLBUYBOTCONF` secret as everything else:
  `SMTP_HOST`, `SMTP_PORT` (default 587), `SMTP_USER`, `SMTP_PASSWORD`, optional `SMTP_FROM`,
  and `REPORT_EMAIL_TO` (defaults to the shop's Prom-registered address). There is deliberately no
  local-credentials fallback.
- Writing report tabs is `StockManager.create_report` / `replace_report`, so both jobs share one path;
  do not call `gspread.add_worksheet` directly from a job again.
