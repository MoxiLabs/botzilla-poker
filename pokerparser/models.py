"""Data models for poker freeroll tournaments"""

from typing import TypedDict, Optional
from datetime import date, time


class TournamentEvent(TypedDict):
    """Represents a poker freeroll tournament event"""
    date: date
    time: Optional[time]  # None if all-day event
    is_all_day: bool
    room: str
    name: str
    prize: str
    password: str
    source: str
    url: Optional[str]
