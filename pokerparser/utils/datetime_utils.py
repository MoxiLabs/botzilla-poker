"""Date, time and timezone utilities for Botzilla."""

import re
from datetime import datetime, date, time
from typing import Optional
from zoneinfo import ZoneInfo


def get_now_in_tz(tz_name: str = "Europe/Budapest") -> datetime:
    """Get current datetime in the specified timezone."""
    return datetime.now(ZoneInfo(tz_name))


def to_tz_aware(dt: datetime, tz_name: str = "Europe/Budapest") -> datetime:
    """Make datetime timezone aware in given timezone if naive, or convert if aware."""
    target_tz = ZoneInfo(tz_name)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=target_tz)
    return dt.astimezone(target_tz)


def get_discord_timestamp(dt: datetime, tz_name: str = "Europe/Budapest") -> int:
    """Get unix epoch timestamp for Discord <t:...:R> tags."""
    aware = to_tz_aware(dt, tz_name)
    return int(aware.timestamp())


def parse_prize_value(prize_str: str) -> int:
    """Extract numeric integer value from prize string (e.g. '$1,000 GTD' -> 1000)."""
    if not prize_str:
        return 0
    try:
        clean_str = prize_str.replace(",", "").replace(".", "")
        match = re.search(r"\d+", clean_str)
        if match:
            return int(match.group())
    except Exception:
        pass
    return 0
