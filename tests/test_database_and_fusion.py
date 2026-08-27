"""Unit tests for Database batching, Cross-source tournament fusion, and Paginator."""

import os
import shutil
import tempfile
import unittest
from datetime import date, time
from unittest.mock import AsyncMock, MagicMock
import discord

from pokerparser.domain.models import Tournament
from pokerparser.domain.poker_room import PokerRoom
from pokerparser.domain.prize import Prize
from pokerparser.storage.database import Database
from pokerparser.storage.repository import EventRepository
from pokerparser.services.alert_service import AlertService
from pokerparser.config.settings import AlertThresholds
from pokerparser.scrapers.manager import merge_tournaments
from pokerparser.bot.ui.views import FreerollPaginatorView


class TestDatabaseAndFusion(unittest.IsolatedAsyncioTestCase):
    """Test suite verifying database batching, tournament fusion, and paginator logic."""

    async def asyncSetUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_batch.db")
        self.db = Database(db_path=self.db_path)
        await self.db.init_db()
        self.repo = EventRepository(database=self.db)
        self.alert_service = AlertService(repository=self.repo, thresholds=AlertThresholds())

    async def asyncTearDown(self):
        await self.db.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _sample_tournament(self, name="Tourney 1", room="PokerStars", hour=18) -> Tournament:
        return Tournament.from_raw(
            name=name,
            room=room,
            date=date(2026, 8, 28),
            time=time(hour, 0),
            is_all_day=False,
            prize="$100",
            source="test_source",
        )

    async def test_batch_get_unnotified_and_add_sent_events(self):
        """Test batch query and insertion in EventRepository and AlertService."""
        t1 = self._sample_tournament(name="Event 1", hour=10)
        t2 = self._sample_tournament(name="Event 2", hour=12)
        t3 = self._sample_tournament(name="Event 3", hour=14)

        # 1. All should be unnotified initially
        unnotified = await self.alert_service.get_unnotified_events([t1, t2, t3])
        self.assertEqual(len(unnotified), 3)

        # 2. Mark t1 and t2 as sent in batch
        await self.alert_service.mark_events_sent([t1, t2])

        # 3. Subsequent check should only return t3
        remaining = await self.alert_service.get_unnotified_events([t1, t2, t3])
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].name, "Event 3")

    def test_merge_tournaments_fusion(self):
        """Test merging identical tournaments across multiple sources."""
        t_pass = Tournament.from_raw(
            name="Daily Freeroll $500",
            room="GGPoker",
            date=date(2026, 8, 28),
            time=time(20, 0),
            is_all_day=False,
            prize="$500",
            password="not required",
            source="freerollpass.com",
            url="https://freerollpass.com/1",
        )

        t_password = Tournament.from_raw(
            name="Daily Freeroll $500",
            room="gg",
            date=date(2026, 8, 28),
            time=time(20, 0),
            is_all_day=False,
            prize="$500",
            password="secret_password_123",
            source="freeroll-password.com",
            url="https://freeroll-password.com/2",
        )

        t_other = self._sample_tournament(name="Other Unique Tournament", room="888poker", hour=22)

        merged = merge_tournaments([t_pass, t_password, t_other])

        # Should merge 2 duplicate tournaments into 1 + 1 unique = 2 total
        self.assertEqual(len(merged), 2)

        gg_event = next(e for e in merged if e.room.clean_id == "ggpoker")
        self.assertEqual(gg_event.password, "secret_password_123")
        self.assertIn("freerollpass.com", gg_event.source)
        self.assertIn("freeroll-password.com", gg_event.source)

    async def test_paginator_view_filtering(self):
        """Test FreerollPaginatorView pagination and room filtering."""
        t1 = self._sample_tournament(name="PS 1", room="PokerStars", hour=10)
        t2 = self._sample_tournament(name="PS 2", room="PokerStars", hour=12)
        t3 = self._sample_tournament(name="GG 1", room="GGPoker", hour=14)

        from pokerparser.bot.ui.components import TournamentComponentBuilder
        builder = TournamentComponentBuilder()

        paginator = FreerollPaginatorView(
            tournaments=[t1, t2, t3],
            component_builder=builder,
            author_id=12345,
        )

        self.assertEqual(len(paginator.all_tournaments), 3)
        self.assertEqual(len(paginator.filtered_tournaments), 3)
        self.assertEqual(paginator.current_tournament, t1)

        # Simulate next page
        mock_interaction = MagicMock()
        mock_interaction.response.edit_message = AsyncMock()
        await paginator._on_next(mock_interaction)
        self.assertEqual(paginator.current_page, 1)
        self.assertEqual(paginator.current_tournament, t2)
        mock_interaction.response.edit_message.assert_called_once()


    async def test_timed_alerts_and_cleanup_with_event_hash(self):
        """Test AlertService deduplication using event_hash and in-memory cache cleanup."""
        from datetime import datetime, timedelta

        now = datetime(2026, 8, 28, 12, 0)
        # Event starting at 12:08 (in 8 mins -> urgent)
        t_urgent = Tournament.from_raw(
            name="Daily Turbo",
            room="PokerStars",
            date=now.date(),
            time=time(12, 8),
            is_all_day=False,
            prize="$100",
        )
        # Another event with the same name at same time but in different room
        t_urgent_gg = Tournament.from_raw(
            name="Daily Turbo",
            room="GGPoker",
            date=now.date(),
            time=time(12, 8),
            is_all_day=False,
            prize="$100",
        )

        due = self.alert_service.get_due_timed_alerts([t_urgent, t_urgent_gg], now=now)
        self.assertEqual(len(due), 2)
        self.assertEqual(due[0][1], "urgent")
        self.assertEqual(due[1][1], "urgent")

        # Mark t_urgent as sent
        self.alert_service.mark_timed_alert_sent(t_urgent, "urgent", sent_at=now)

        # Subsequent check should now only return t_urgent_gg
        due_next = self.alert_service.get_due_timed_alerts([t_urgent, t_urgent_gg], now=now)
        self.assertEqual(len(due_next), 1)
        self.assertEqual(due_next[0][0].room.name, "GGPoker")

        # Test cleanup pruning
        past_time = now + timedelta(hours=3)
        await self.alert_service.cleanup(today=now.date(), current_time=past_time)
        self.assertEqual(len(self.alert_service._sent_alerts), 0)

    async def test_alert_service_boundary_thresholds(self):
        """Test AlertService exact threshold boundaries (urgent < 10 min, warning 10..60 min)."""
        from datetime import datetime, timedelta

        now = datetime(2026, 8, 28, 12, 0)
        # Helper to create tourneys with delta minutes
        def make_t(name: str, delta_minutes: int, is_all_day: bool = False):
            target_dt = now + timedelta(minutes=delta_minutes)
            return Tournament.from_raw(
                name=name,
                room="PokerStars",
                date=target_dt.date(),
                time=target_dt.time() if not is_all_day else None,
                is_all_day=is_all_day,
                prize="$100",
            )

        t_past = make_t("Past Tourney", -1)
        t_urgent_0 = make_t("Urgent 0min", 0)
        t_urgent_9 = make_t("Urgent 9min", 9)
        t_warning_10 = make_t("Warning 10min", 10)
        t_warning_59 = make_t("Warning 59min", 59)
        t_future_60 = make_t("Future 60min", 60)
        t_future_120 = make_t("Future 120min", 120)
        t_allday = make_t("All Day Event", 5, is_all_day=True)

        events = [t_past, t_urgent_0, t_urgent_9, t_warning_10, t_warning_59, t_future_60, t_future_120, t_allday]
        due = self.alert_service.get_due_timed_alerts(events, now=now)

        due_dict = {t.name: alert_type for t, alert_type, _ in due}

        # Assertions
        self.assertNotIn("Past Tourney", due_dict)
        self.assertEqual(due_dict.get("Urgent 0min"), "urgent")
        self.assertEqual(due_dict.get("Urgent 9min"), "urgent")
        self.assertEqual(due_dict.get("Warning 10min"), "warning")
        self.assertEqual(due_dict.get("Warning 59min"), "warning")
        self.assertNotIn("Future 60min", due_dict)
        self.assertNotIn("Future 120min", due_dict)
        self.assertNotIn("All Day Event", due_dict)

    async def test_repository_chunked_query(self):
        """Test EventRepository handles large batch sizes with parameter chunking."""
        tournaments = [
            self._sample_tournament(name=f"Bulk Event {i}", hour=10 + (i % 10))
            for i in range(250)
        ]
        # Query unnotified with chunk_size=50
        unnotified = await self.repo.get_unnotified_events(tournaments, chunk_size=50)
        self.assertEqual(len(unnotified), 250)

        # Insert first 150 items with chunk_size=50
        await self.repo.add_sent_events(tournaments[:150], chunk_size=50)

        # Query again -> should have 100 remaining
        remaining = await self.repo.get_unnotified_events(tournaments, chunk_size=50)
        self.assertEqual(len(remaining), 100)


if __name__ == "__main__":
    unittest.main()
