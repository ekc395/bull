"""Trading-day time helpers (NYSE / US-Eastern).

The cache key for verdicts and per-day tool caches is the *trading session date*
in US/Eastern, not the user's local date. A verdict generated at 6pm PST (9pm ET)
belongs to that day's trading session; one generated at 10pm PST (1am ET the next
day) belongs to the next session.

Timestamps are stored in the DB as UTC (tz-aware). These helpers convert between
"now / today in ET" and the UTC window used for range queries.
"""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def now_utc() -> datetime:
    """Current instant as a tz-aware UTC datetime. Use as a `default=` for columns."""
    return datetime.now(timezone.utc)


def trading_day(now: datetime | None = None) -> date:
    """ET calendar date for `now` (defaults to current instant).

    Naive datetimes are assumed to already be UTC.
    """
    if now is None:
        now = now_utc()
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(ET).date()


def trading_day_bounds(d: date) -> tuple[datetime, datetime]:
    """UTC `[start, end)` window covering ET calendar date `d`."""
    start_et = datetime.combine(d, time.min, tzinfo=ET)
    end_et = start_et + timedelta(days=1)
    return start_et.astimezone(timezone.utc), end_et.astimezone(timezone.utc)
