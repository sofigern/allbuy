"""Time handling for Prom timestamps.

Prom reports order times in two different shapes, and mixing them up is the
failure mode this module exists to prevent:

* the public API returns ``date_created`` in ISO-8601 **with an offset**,
  and for this account that offset is UTC - a live ``/orders/list`` call on
  2026-09-11 returned ``2026-09-11T15:20:57.225474+00:00`` for an order
  placed at 18:20 Kyiv;
* the seller cabinet renders the same instant as a **naive Kyiv wall clock**.

Every timestamp is therefore normalised to an aware ``Europe/Kyiv`` datetime
at the edge, and a naive value is read as Kyiv rather than as the host's
local zone, which on a UTC container would be three hours adrift in summer.
"""

import datetime
from zoneinfo import ZoneInfo

KYIV = ZoneInfo("Europe/Kyiv")

#: The daily report boundary the owner asked for.
REPORT_TIME = datetime.time(hour=8, minute=50)


def to_kyiv(value: str | None) -> datetime.datetime | None:
    """Parse a Prom timestamp into an aware Europe/Kyiv datetime."""
    if not value:
        return None

    parsed = datetime.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=KYIV)
    return parsed.astimezone(KYIV)


def now_kyiv() -> datetime.datetime:
    return datetime.datetime.now(KYIV)


def daily_window(
    now: datetime.datetime,
    at: datetime.time = REPORT_TIME,
) -> tuple[datetime.datetime, datetime.datetime]:
    """Return the ``[start, end)`` 24-hour window ending at the last ``at``.

    Run at 08:50 this yields 08:50 yesterday up to, but not including,
    08:50 today. The boundary is half-open so consecutive runs neither
    drop nor double-count an order that lands exactly on it.
    """
    now = now.astimezone(KYIV) if now.tzinfo else now.replace(tzinfo=KYIV)

    end = now.replace(
        hour=at.hour, minute=at.minute, second=0, microsecond=0
    )
    if end > now:
        end -= datetime.timedelta(days=1)

    return end - datetime.timedelta(days=1), end
