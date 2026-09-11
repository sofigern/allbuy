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
- **Timezones.** Prom's public API returns `date_created` **in UTC** — measured, not assumed: a live
  `/orders/list` call on 2026-09-11 returned `2026-09-11T15:20:57.225474+00:00` for an order placed at
  18:20 Kyiv. The seller cabinet renders the same instant as a naive Kyiv wall clock. `src/clock.to_kyiv` normalises both to aware Europe/Kyiv, and
  `Order.datetime_created` / `Order.age` go through it. Before this, `Order` stripped the offset and
  compared it against a local `datetime.now()`, so every age was out by exactly that 3 h offset.
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
- **Both outputs are off unless `--apply` is passed.** Without it the run prints the worksheet title,
  the attachment filename, and the exact email body. The scheduled invocation must pass `--apply`.
- The email carries the report as an **.xlsx attachment** (`build_workbook`, `openpyxl`), not as text in
  the body — the owner reads it as a purchase proposal he wants to sort/filter, not read in a mail client.
  `openpyxl` was picked over `xlsxwriter` because it can also read (useful if a future job ever needs to
  re-parse a sent report) and is the more widely maintained of the two; either would have worked here.
  The body still stands on its own (window, SKU count, short count) because a phone preview shows the
  body, not the attachment. The attachment reuses the same rows/header as the worksheet tab
  (`row.as_row()`, untruncated names) so the two never drift apart.
  The filename is the worksheet `title` (already `YYYY-MM-DD HH-MM …`, so a year of them sorts correctly)
  plus `.xlsx`. `MailSender.build` takes an optional `attachment: tuple[filename, bytes]` — extended in
  place rather than adding a second sender.
- SMTP settings come from the same `ALLBUYBOTCONF` secret as everything else:
  `SMTP_HOST`, `SMTP_PORT` (default 587), `SMTP_USER`, `SMTP_PASSWORD`, optional `SMTP_FROM`,
  and `REPORT_EMAIL_TO` (defaults to the shop's Prom-registered address). There is deliberately no
  local-credentials fallback.
- Writing report tabs is `StockManager.create_report` / `replace_report`. `daily_stock.py` uses them;
  `leftowers.py` still has its own inline `gspread` calls and is deliberately left alone, because the
  owner wants the leftovers job untouched. Migrate it only when there is a reason to touch it anyway.

- `quantity` on an order line is a **float** (`1.0`, confirmed on a live call), so it is rendered
  through `format_quantity`; printing it raw puts "1.0" in the report.

## Alerting

The shop bot has no messenger. Signal - the `signal-cli-rest-api` Cloud Run
service and the `src/signal` package - was removed once it stopped being used;
what it used to send now goes to the log.

One of those lines is load-bearing. When prom's cookies go stale the bot stops
processing orders, and the only thing that says so is

    logger.error("COOKIES_EXPIRED: ...")

in `__main__.py`. A Cloud Logging alerting policy in GCP project `all-buy-tools`
(`projects/all-buy-tools/alertPolicies/15861306608002817826`, condition filters
on `resource.type="cloud_run_job" AND resource.labels.job_name="shop-orders-refresh"
AND textPayload:"COOKIES_EXPIRED"`) matches that prefix and emails the owner
through notification channel `projects/all-buy-tools/notificationChannels/8444333370555292492`
(sofigenr@gmail.com). Verified live by writing a matching test log entry with
`gcloud logging write` and confirming it matched the policy filter.
**Changing the string silently disables the alert** - the job keeps exiting
cleanly and nobody is told the shop has stopped. The notification channel is
`verificationStatus: VERIFIED` as of 2026-09-11 (the owner completed GCP's
email verification code flow), and a test log entry written after that
verification matched the policy filter, confirming the log-match -> channel
wiring end to end. There is still no API to list fired incidents for a policy;
the only way to re-check that an email actually lands is a test log write
(`gcloud logging write`, matching the filter above) plus looking in
sofigenr@gmail.com by hand.

The six `SIGNAL_*`/`ADMIN_PHONE` keys are gone from the `ALLBUYBOTCONF` secret
as of version 16 (2026-09-11, added as a new version off v15 once PR #5's image
had already run cleanly once); it now holds only `COOKIES`, `PROM_TOKEN`,
`REPORT_EMAIL_TO`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`,
`SMTP_FROM`. The `signal-cli-rest-api` Cloud Run service and its
`signal-cli-rest-api-*` revisions are deleted (2026-09-11, europe-central2);
nothing in this repo calls it any more.

If Signal is ever wanted back, standing the service up again is not a redeploy,
it is a from-scratch re-link. It was `bbernhard/signal-cli-rest-api:latest`,
1 CPU / 1Gi, `MODE=native`, `AUTO_RECEIVE_SCHEDULE=0 * * * *`, `maxScale=1`,
running as `all-buy-service-account@all-buy-tools.iam.gserviceaccount.com`,
with its `/home/.local/share/signal-cli` state on a GCS FUSE mount backed by
the `signal-local-bucket` bucket. That bucket - and with it the linked-device
registration for the phone number Signal sent from, plus its chat history,
attachments, avatars, and sticker packs - was deleted on 2026-09-11 (owner's
call, "Локал бакет нахер."): 202 objects, ~50 MiB, in four prefixes -
`attachments/` (94 media files), `avatars/` (12 contact/group/profile images),
`data/` (signal-cli's own account state: `accounts.json` plus two linked
accounts' `account.db`, one with a `msg-cache`), `stickers/` (3 packs). Nothing
else referenced the bucket (checked: no Cloud Run service or job volume mount,
no code path) before it went. A future Signal rebuild means linking a fresh
device from zero (scanning a QR code again) - there is no bucket left to
redeploy against.

## Scheduling (all of it lives in GCP, not in this repo)

`cloudbuild.yaml` only builds and pushes `gcr.io/all-buy-tools/my-image:latest`. What runs, when, is
a pair of Cloud Run Jobs and Cloud Scheduler triggers in **`europe-central2`** of project
**`all-buy-tools`**, all on that one image:

| Cloud Run Job | args | Scheduler trigger | schedule | tz |
|---|---|---|---|---|
| `stock-leftovers` | `python leftowers.py` | `stock-leftovers-scheduler-trigger` | `30 11,19 * * *` | `Europe/Kiev` |
| `shop-orders-refresh` | image default (`__main__.py`) | `shop-orders-refresh-scheduler-trigger` | `*/10 * * * *` | `Etc/UTC` |
| `daily-stock` | `python daily_stock.py --apply` | `daily-stock-scheduler-trigger` | `50 8 * * *` | `Europe/Kiev` |
| — | — | `all-buy-bot-scheduler-trigger` | `*/10 * * * *` | `Etc/UTC` |

Note the leftovers job runs **twice daily at 11:30 and 19:30 Kyiv**, not once in the morning.

Each trigger is an HTTP POST to
`https://europe-central2-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/all-buy-tools/jobs/<job>:run`.

To change a job's time, edit only its own trigger — the schedules are independent:

```
gcloud scheduler jobs update http <trigger-name> \
  --location=europe-central2 --schedule="50 8 * * *" --time-zone="Europe/Kiev"
```

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
