from datetime import date
from typing import Optional, List, Set
import aiosqlite

from ..domain.models import Tournament
from .database import Database


class EventRepository:
    """Repository handling persistence and lookup of sent events with persistent connections."""

    def __init__(self, database: Database):
        self.db = database

    async def is_event_sent(self, event: Tournament) -> bool:
        """Check if an event hash exists in the database."""
        event_hash = event.event_hash
        conn = await self.db.get_connection()
        async with conn.execute(
            "SELECT 1 FROM sent_events WHERE event_hash = ?", (event_hash,)
        ) as cursor:
            return (await cursor.fetchone()) is not None

    async def get_unnotified_events(
        self, events: List[Tournament], chunk_size: int = 200
    ) -> List[Tournament]:
        """Batch lookup in safe parameter chunks returning only unnotified tournaments."""
        if not events:
            return []

        event_map = {e.event_hash: e for e in events}
        hashes = list(event_map.keys())
        sent_hashes: Set[str] = set()
        conn = await self.db.get_connection()

        for i in range(0, len(hashes), chunk_size):
            chunk = hashes[i : i + chunk_size]
            placeholders = ",".join("?" for _ in chunk)
            async with conn.execute(
                f"SELECT event_hash FROM sent_events WHERE event_hash IN ({placeholders})", chunk
            ) as cursor:
                rows = await cursor.fetchall()
                sent_hashes.update(row[0] for row in rows)

        return [e for h, e in event_map.items() if h not in sent_hashes]

    async def add_sent_event(self, event: Tournament):
        """Record an event as sent."""
        await self.add_sent_events([event])

    async def add_sent_events(self, events: List[Tournament], chunk_size: int = 200):
        """Batch record multiple events as sent in safe chunks."""
        if not events:
            return

        data = [(e.event_hash, e.date.isoformat()) for e in events]
        conn = await self.db.get_connection()
        for i in range(0, len(data), chunk_size):
            chunk = data[i : i + chunk_size]
            await conn.executemany(
                "INSERT OR IGNORE INTO sent_events (event_hash, event_date) VALUES (?, ?)",
                chunk,
            )
        await conn.commit()

    async def has_sent_today(self, target_date: date) -> bool:
        """Check if any event has been sent on the target date."""
        date_str = target_date.isoformat()
        conn = await self.db.get_connection()
        async with conn.execute(
            "SELECT 1 FROM sent_events WHERE event_date = ? LIMIT 1", (date_str,)
        ) as cursor:
            return (await cursor.fetchone()) is not None

    async def cleanup_old_events(self, before_date: date):
        """Remove events sent before the given date."""
        date_str = before_date.isoformat()
        conn = await self.db.get_connection()
        await conn.execute(
            "DELETE FROM sent_events WHERE event_date < ?", (date_str,)
        )
        await conn.commit()
