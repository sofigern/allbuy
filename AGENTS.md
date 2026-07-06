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
