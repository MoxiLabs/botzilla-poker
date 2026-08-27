"""SQLite database connection and setup for Botzilla."""

import os
import aiosqlite
from typing import Optional


class Database:
    """Handles SQLite database connection and table initialization with persistent connection support."""

    def __init__(self, db_path: str = "botzilla.db"):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def init_db(self):
        """Creates required tables if they do not exist."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        conn = await self.get_connection()
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sent_events (
                event_hash TEXT PRIMARY KEY,
                event_date DATE NOT NULL
            )
            """
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sent_events_date ON sent_events(event_date)"
        )
        await conn.commit()

    async def get_connection(self) -> aiosqlite.Connection:
        """Returns the active persistent SQLite connection with auto-reconnect support."""
        if self._connection is None:
            self._connection = await aiosqlite.connect(self.db_path)
            return self._connection

        # Verify connection liveness and reconnect if closed/invalid
        try:
            async with self._connection.execute("SELECT 1"):
                pass
        except Exception:
            try:
                await self._connection.close()
            except Exception:
                pass
            self._connection = await aiosqlite.connect(self.db_path)

        return self._connection

    async def close(self):
        """Closes the persistent SQLite connection gracefully."""
        if self._connection is not None:
            try:
                await self._connection.close()
            except Exception:
                pass
            self._connection = None

    def connect(self) -> aiosqlite.Connection:
        """Fallback context manager for one-off standalone usage."""
        return aiosqlite.connect(self.db_path)
