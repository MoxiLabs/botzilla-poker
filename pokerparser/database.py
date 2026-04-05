import aiosqlite
import hashlib
import json
import os
from datetime import date
from typing import Dict, Any

from .models import TournamentEvent

# Determine DB path relative to the project root (parent of pokerparser)
DB_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "botzilla.db")

def get_event_hash(event: TournamentEvent) -> str:
    """Generate a unique SHA256 hash for a tournament event."""
    data = {
        "date": event["date"].isoformat(),
        "time": event["time"].isoformat() if event["time"] else None,
        "is_all_day": event["is_all_day"],
        "room": event["room"],
        "name": event["name"],
        "prize": event["prize"],
        "password": event["password"],
        "source": event.get("source", "n/a")
    }
    data_str = json.dumps(data, sort_keys=True)
    return hashlib.sha256(data_str.encode('utf-8')).hexdigest()

async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sent_events (
                event_hash TEXT PRIMARY KEY,
                event_date DATE NOT NULL
            )
        """)
        await db.commit()

async def is_event_sent(event: TournamentEvent) -> bool:
    event_hash = get_event_hash(event)
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT 1 FROM sent_events WHERE event_hash = ?", (event_hash,)) as cursor:
            return await cursor.fetchone() is not None

async def add_sent_event(event: TournamentEvent):
    event_hash = get_event_hash(event)
    event_date = event["date"].isoformat()
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("INSERT OR IGNORE INTO sent_events (event_hash, event_date) VALUES (?, ?)", (event_hash, event_date))
        await db.commit()

async def has_sent_today(target_date: date) -> bool:
    date_str = target_date.isoformat()
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT 1 FROM sent_events WHERE event_date = ? LIMIT 1", (date_str,)) as cursor:
            return await cursor.fetchone() is not None

async def cleanup_old_events(target_date: date):
    date_str = target_date.isoformat()
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM sent_events WHERE event_date < ?", (date_str,))
        await db.commit()
