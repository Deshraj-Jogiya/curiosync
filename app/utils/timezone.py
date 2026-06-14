"""Timezone utilities for MST / America/Phoenix."""

from datetime import datetime, date
from zoneinfo import ZoneInfo

PHOENIX_TZ = ZoneInfo("America/Phoenix")


def now_phoenix() -> datetime:
    """Current datetime in America/Phoenix (MST year-round, no DST)."""
    return datetime.now(PHOENIX_TZ)


def today_phoenix() -> date:
    """Today's date in America/Phoenix timezone."""
    return now_phoenix().date()


def is_today_phoenix(dt: datetime) -> bool:
    """Check if a datetime falls on today in Phoenix timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=PHOENIX_TZ)
    return dt.astimezone(PHOENIX_TZ).date() == today_phoenix()
