"""Domain models for poker freeroll tournaments."""

from dataclasses import dataclass
from datetime import date, time, datetime
import hashlib
import json
import re
from typing import Optional, Union

from .prize import Prize
from .poker_room import PokerRoom


@dataclass(frozen=True)
class Tournament:
    """Represents an immutable poker freeroll tournament event with Value Objects."""
    name: str
    room: PokerRoom
    date: date
    time: Optional[time]
    is_all_day: bool
    prize: Prize
    password: str = "not required"
    source: str = "unknown"
    url: Optional[str] = None

    @classmethod
    def from_raw(
        cls,
        name: str,
        room: Union[PokerRoom, str],
        date: date,
        time: Optional[time],
        is_all_day: bool,
        prize: Union[Prize, str],
        password: str = "not required",
        source: str = "unknown",
        url: Optional[str] = None,
    ) -> "Tournament":
        """Factory creating a Tournament with automatic normalization of Value Objects."""
        room_obj = room if isinstance(room, PokerRoom) else PokerRoom.from_raw(room)
        prize_obj = prize if isinstance(prize, Prize) else Prize.from_raw(prize)
        return cls(
            name=name,
            room=room_obj,
            date=date,
            time=time,
            is_all_day=is_all_day,
            prize=prize_obj,
            password=password or "not required",
            source=source,
            url=url,
        )

    @property
    def start_datetime(self) -> datetime:
        """Get the start datetime of the tournament."""
        if self.is_all_day or self.time is None:
            return datetime.combine(self.date, time.min)
        return datetime.combine(self.date, self.time)

    @property
    def prize_value(self) -> int:
        """Extract numeric amount of the prize."""
        return self.prize.amount

    @property
    def room_name(self) -> str:
        """Display name of the poker room."""
        return self.room.name

    @property
    def clean_room_name(self) -> str:
        """Sanitized room ID for logo matching."""
        return self.room.clean_id

    @property
    def event_hash(self) -> str:
        """Generate a unique SHA256 hash for deduplication across all scraper sources."""
        clean_name = re.sub(r"\s+", " ", self.name.strip().lower())
        data = {
            "date": self.date.isoformat(),
            "time": self.time.isoformat() if self.time else None,
            "is_all_day": self.is_all_day,
            "room": self.room.clean_id,
            "name": clean_name,
        }
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode("utf-8")).hexdigest()

    @property
    def has_password(self) -> bool:
        """Check if tournament requires a known password."""
        return bool(
            self.password
            and self.password.lower() not in ("not required", "n/a", "none", "")
        )
