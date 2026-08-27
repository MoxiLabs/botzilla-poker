"""Unit tests for Network I/O and ClientSession lifecycle management."""

import asyncio
import os
import shutil
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp
import discord

from pokerparser.scrapers.network.http_client import HttpFetcher
from pokerparser.scrapers.base import BaseScraper
from pokerparser.scrapers.manager import ScraperManager
from pokerparser.services.tournament_service import TournamentService
from pokerparser.bot.ui.assets import AssetManager
from pokerparser.domain.poker_room import PokerRoom


class TestNetworkLifecycle(unittest.IsolatedAsyncioTestCase):
    """Test suite verifying shared ClientSession injection and AssetManager async I/O."""

    async def asyncSetUp(self):
        self.temp_dir = tempfile.mkdtemp()

    async def asyncTearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_http_fetcher_session_property(self):
        """Test HttpFetcher session getter and setter."""
        fetcher = HttpFetcher()
        self.assertIsNone(fetcher.session)

        dummy_session = MagicMock(spec=aiohttp.ClientSession)
        fetcher.session = dummy_session
        self.assertIs(fetcher.session, dummy_session)

    async def test_session_propagation_chain(self):
        """Test session propagation from TournamentService -> ScraperManager -> BaseScraper -> HttpFetcher."""
        scraper1 = BaseScraper(url="https://example.com/1")
        scraper2 = BaseScraper(url="https://example.com/2")
        manager = ScraperManager(scrapers=[scraper1, scraper2])
        service = TournamentService(scraper_manager=manager)

        self.assertIsNone(scraper1.fetcher.session)
        self.assertIsNone(scraper2.fetcher.session)

        dummy_session = MagicMock(spec=aiohttp.ClientSession)
        service.set_session(dummy_session)

        self.assertIs(scraper1.fetcher.session, dummy_session)
        self.assertIs(scraper2.fetcher.session, dummy_session)

    async def test_http_fetcher_uses_shared_session(self):
        """Test that HttpFetcher.fetch_text uses the shared session when provided."""
        fetcher = HttpFetcher()
        mock_session = MagicMock(spec=aiohttp.ClientSession)
        mock_session.closed = False

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.text = AsyncMock(return_value="<html>Mock Content</html>")

        # Async context manager for session.get
        mock_get_ctx = AsyncMock()
        mock_get_ctx.__aenter__.return_value = mock_response
        mock_get_ctx.__aexit__.return_value = None
        mock_session.get.return_value = mock_get_ctx

        fetcher.session = mock_session
        result = await fetcher.fetch_text("https://test-poker.com")

        self.assertEqual(result, "<html>Mock Content</html>")
        mock_session.get.assert_called_once()

    async def test_asset_manager_session_and_existing_logo(self):
        """Test AssetManager logo check when logo already exists locally."""
        asset_mgr = AssetManager(base_dir=self.temp_dir)
        dummy_session = MagicMock(spec=aiohttp.ClientSession)
        asset_mgr.session = dummy_session
        self.assertIs(asset_mgr.session, dummy_session)

        room = PokerRoom.from_raw("PokerStars")
        expected_path = asset_mgr.get_logo_path(room)

        # Create dummy logo file
        with open(expected_path, "wb") as f:
            f.write(b"PNG_DATA")

        path = await asset_mgr.ensure_logo(room)
        self.assertEqual(path, expected_path)
        self.assertTrue(os.path.exists(expected_path))

    async def test_asset_manager_downloads_logo_with_shared_session(self):
        """Test AssetManager downloads logo via shared session when not present."""
        asset_mgr = AssetManager(base_dir=self.temp_dir)
        mock_session = MagicMock(spec=aiohttp.ClientSession)
        mock_session.closed = False

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"DOWNLOADED_PNG")

        mock_get_ctx = AsyncMock()
        mock_get_ctx.__aenter__.return_value = mock_response
        mock_get_ctx.__aexit__.return_value = None
        mock_session.get.return_value = mock_get_ctx

        asset_mgr.session = mock_session
        room = PokerRoom.from_raw("GGPoker")
        expected_path = asset_mgr.get_logo_path(room)

        path = await asset_mgr.ensure_logo(room)
        self.assertEqual(path, expected_path)
        self.assertTrue(os.path.exists(expected_path))
        with open(expected_path, "rb") as f:
            self.assertEqual(f.read(), b"DOWNLOADED_PNG")

    async def test_bot_session_lifecycle(self):
        """Test PokerBot creates session in setup_hook and closes it on close()."""
        from pokerparser.config.settings import Settings
        from pokerparser.bot.client import create_bot

        cfg = Settings(discord_token="test_token", dry_run=True, db_file=os.path.join(self.temp_dir, "test.db"))
        bot = create_bot(cfg)

        self.assertIsNone(bot.http_session)
        with patch.object(bot, "load_extension", new=AsyncMock()), \
             patch.object(bot.database, "init_db", new=AsyncMock()):
            await bot.setup_hook()
            self.assertIsNotNone(bot.http_session)
            self.assertFalse(bot.http_session.closed)
            self.assertIs(bot.tournament_service.scraper_manager.scrapers[0].fetcher.session, bot.http_session)
            self.assertIs(bot.component_builder.asset_manager.session, bot.http_session)

            await bot.close()
            self.assertTrue(bot.http_session.closed)

    async def test_command_suffix_aliases(self):
        """Test that setting command_suffix registers aliases exclusively on admin cog."""
        from pokerparser.config.settings import Settings
        from pokerparser.bot.client import create_bot

        cfg = Settings(
            discord_token="test_token",
            command_suffix="_dev",
            dry_run=True,
            db_file=os.path.join(self.temp_dir, "test.db"),
        )
        bot = create_bot(cfg)

        await bot.database.init_db()
        await bot.load_extension("pokerparser.bot.cogs.admin")
        await bot.load_extension("pokerparser.bot.cogs.commands")

        admin_cog = bot.get_cog("AdminCommands")
        self.assertIn("sync_dev", admin_cog.sync_commands.aliases)
        self.assertIn("clear_commands_dev", admin_cog.clear_commands.aliases)

        poker_cog = bot.get_cog("PokerCommands")
        self.assertEqual(poker_cog.cmd_day.aliases, [])
        self.assertEqual(poker_cog.cmd_next.aliases, [])

        await bot.close()

    async def test_tournament_service_filter_tournaments(self):
        """Test TournamentService filtering by poker room and min_prize threshold."""
        from datetime import date, time
        from pokerparser.domain.models import Tournament

        t1 = Tournament.from_raw("PS Small", "PokerStars", date(2026, 8, 28), time(10, 0), False, "$50")
        t2 = Tournament.from_raw("PS Big", "PokerStars", date(2026, 8, 28), time(12, 0), False, "$500")
        t3 = Tournament.from_raw("GG Big", "GGPoker", date(2026, 8, 28), time(14, 0), False, "$1000")

        service = TournamentService(scraper_manager=MagicMock())

        # Filter by room
        ps_only = service.filter_tournaments([t1, t2, t3], room="pokerstars")
        self.assertEqual(len(ps_only), 2)
        self.assertEqual([t.name for t in ps_only], ["PS Small", "PS Big"])

        # Filter by min_prize
        high_rollers = service.filter_tournaments([t1, t2, t3], min_prize=500)
        self.assertEqual(len(high_rollers), 2)
        self.assertEqual([t.name for t in high_rollers], ["PS Big", "GG Big"])

        # Filter by both
        gg_high = service.filter_tournaments([t1, t2, t3], room="gg", min_prize=500)
        self.assertEqual(len(gg_high), 1)
        self.assertEqual(gg_high[0].name, "GG Big")

    async def test_tournament_service_get_upcoming_and_next(self):
        """Test TournamentService get_upcoming_tournaments and get_next_tournament async methods."""
        from datetime import datetime, timedelta
        from pokerparser.domain.models import Tournament

        now = datetime.now()
        # Create events at various times
        t_past = Tournament.from_raw(
            "Past Event", "PokerStars", (now - timedelta(hours=2)).date(), (now - timedelta(hours=2)).time(), False, "$100"
        )
        t_near = Tournament.from_raw(
            "Near Future", "PokerStars", (now + timedelta(hours=2)).date(), (now + timedelta(hours=2)).time(), False, "$100"
        )
        t_mid = Tournament.from_raw(
            "Mid Future High", "GGPoker", (now + timedelta(hours=10)).date(), (now + timedelta(hours=10)).time(), False, "$1000"
        )
        t_far = Tournament.from_raw(
            "Far Future", "888poker", (now + timedelta(hours=30)).date(), (now + timedelta(hours=30)).time(), False, "$50"
        )
        t_allday = Tournament.from_raw(
            "All Day Tomorrow", "Unibet", (now + timedelta(days=1)).date(), None, True, "$500"
        )

        mock_manager = MagicMock()
        mock_manager.fetch_all = AsyncMock(return_value=[t_past, t_near, t_mid, t_far, t_allday])
        service = TournamentService(scraper_manager=mock_manager)

        # 1. get_upcoming_tournaments (default 24 hours)
        upcoming_24h = await service.get_upcoming_tournaments(hours=24)
        upcoming_names = [t.name for t in upcoming_24h]
        self.assertIn("Near Future", upcoming_names)
        self.assertIn("Mid Future High", upcoming_names)
        self.assertIn("All Day Tomorrow", upcoming_names)
        self.assertNotIn("Past Event", upcoming_names)
        self.assertNotIn("Far Future", upcoming_names)

        # 2. get_upcoming_tournaments with room and min_prize filters
        filtered_upcoming = await service.get_upcoming_tournaments(hours=24, room="gg", min_prize=500)
        self.assertEqual(len(filtered_upcoming), 1)
        self.assertEqual(filtered_upcoming[0].name, "Mid Future High")

        # 3. get_next_tournament (should pick nearest timed tournament, ignoring all-day)
        next_t = await service.get_next_tournament()
        self.assertIsNotNone(next_t)
        self.assertEqual(next_t.name, "Near Future")

        # 4. get_next_tournament with filter
        next_gg = await service.get_next_tournament(room="gg")
        self.assertIsNotNone(next_gg)
        self.assertEqual(next_gg.name, "Mid Future High")

        # 5. get_next_tournament when no match
        next_none = await service.get_next_tournament(room="nonexistent_room")
        self.assertIsNone(next_none)

    def test_create_default_scrapers_factory(self):
        """Test create_default_scrapers builds scrapers configured from URLs."""
        from pokerparser.scrapers import create_default_scrapers

        scrapers = create_default_scrapers(
            url_password="https://custom-pw.com",
            url_pass="https://custom-pass.com",
            timezone="Europe/Budapest",
        )
        self.assertEqual(len(scrapers), 2)
        self.assertEqual(scrapers[0].url, "https://custom-pw.com")
        self.assertEqual(scrapers[1].url, "https://custom-pass.com")

    async def test_bot_on_command_error_handlers(self):
        """Test PokerBot.on_command_error handles cooldown, permissions, and check failures gracefully."""
        from discord.ext import commands
        from pokerparser.config.settings import Settings
        from pokerparser.bot.client import create_bot

        cfg = Settings(discord_token="dummy", dry_run=True, db_file=os.path.join(self.temp_dir, "err_test.db"))
        bot = create_bot(cfg)

        mock_ctx = MagicMock()
        mock_ctx.command = "day"
        mock_ctx.send = AsyncMock()

        # 1. Cooldown error
        cooldown_err = commands.CommandOnCooldown(commands.Cooldown(1, 5), 3.5, commands.BucketType.user)
        await bot.on_command_error(mock_ctx, cooldown_err)
        mock_ctx.send.assert_called_once()
        self.assertIn("3.5", mock_ctx.send.call_args[0][0])

        # 2. Permission error
        mock_ctx.send.reset_mock()
        perm_err = commands.MissingPermissions(["administrator"])
        await bot.on_command_error(mock_ctx, perm_err)
        mock_ctx.send.assert_called_once()

        # 3. Channel restriction error
        mock_ctx.send.reset_mock()
        check_err = commands.CheckFailure("Channel not allowed")
        await bot.on_command_error(mock_ctx, check_err)
        mock_ctx.send.assert_called_once()

        await bot.close()

    async def test_broadcaster_send_message_exception_resilience(self):
        """Test DiscordBroadcaster catches and logs Forbidden and HTTPException without raising."""
        from pokerparser.bot.broadcaster import DiscordBroadcaster
        from pokerparser.config.settings import Settings

        cfg = Settings(dry_run=False)
        broadcaster = DiscordBroadcaster(
            bot=MagicMock(),
            settings=cfg,
            alert_service=MagicMock(),
            component_builder=MagicMock(),
            event_bus=MagicMock(),
        )

        mock_target = MagicMock()
        mock_target.send = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "Cannot send"))

        # Should catch Forbidden and not raise
        await broadcaster.send_message(mock_target, content="Test Forbidden")
        mock_target.send.assert_called_once()


    async def test_tournament_service_cache_ttl(self):
        """Test TournamentService auto-expires cache after TTL seconds."""
        from datetime import datetime, timedelta
        from pokerparser.domain.models import Tournament

        mock_manager = MagicMock()
        mock_manager.fetch_all = AsyncMock(return_value=[
            Tournament.from_raw("Test Tourney", "PokerStars", datetime.now().date(), None, True, "$100")
        ])
        service = TournamentService(scraper_manager=mock_manager, cache_ttl_seconds=10)

        # First call fetches from scrapers
        tournaments = await service.get_all_tournaments()
        self.assertEqual(len(tournaments), 1)
        mock_manager.fetch_all.assert_called_once()

        # Second call within TTL uses cache without fetching
        await service.get_all_tournaments()
        mock_manager.fetch_all.assert_called_once()

        # Simulate TTL expiration
        service._last_fetched = datetime.now() - timedelta(seconds=15)
        self.assertTrue(service.is_cache_expired)

        # Third call after TTL re-fetches automatically
        await service.get_all_tournaments()
        self.assertEqual(mock_manager.fetch_all.call_count, 2)

    async def test_asset_manager_failed_download_caching(self):
        """Test AssetManager caches failed logo downloads to prevent hammering CDN."""
        asset_mgr = AssetManager(base_dir=self.temp_dir, max_concurrency=2)
        mock_session = MagicMock()
        mock_session.closed = False

        # 404 response
        mock_resp = AsyncMock()
        mock_resp.status = 404
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_resp
        mock_ctx.__aexit__.return_value = None
        mock_session.get.return_value = mock_ctx

        asset_mgr.session = mock_session
        room = PokerRoom.from_raw("UnknownRoom404")

        # First call attempts download and fails
        path1 = await asset_mgr.ensure_logo(room)
        self.assertIsNone(path1)
        mock_session.get.assert_called_once()

        # Second call does not attempt download due to failure cache
        path2 = await asset_mgr.ensure_logo(room)
        self.assertIsNone(path2)
        mock_session.get.assert_called_once()


    async def test_circuit_breaker_states(self):
        """Test CircuitBreaker state transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)."""
        from datetime import datetime, timedelta
        from pokerparser.scrapers.network.circuit_breaker import CircuitBreaker, CircuitState

        breaker = CircuitBreaker(name="test_breaker", failure_threshold=2, cooldown_seconds=60)
        self.assertEqual(breaker.state, CircuitState.CLOSED)
        self.assertTrue(breaker.can_execute())

        # 1st failure
        breaker.record_failure(RuntimeError("HTTP 500"))
        self.assertEqual(breaker.state, CircuitState.CLOSED)

        # 2nd failure -> trips to OPEN
        breaker.record_failure(RuntimeError("HTTP 500"))
        self.assertEqual(breaker.state, CircuitState.OPEN)
        self.assertFalse(breaker.can_execute())

        # After cooldown -> transitions to HALF_OPEN
        future_time = datetime.now() + timedelta(seconds=65)
        self.assertTrue(breaker.can_execute(now=future_time))
        self.assertEqual(breaker.state, CircuitState.HALF_OPEN)

        # Success in HALF_OPEN -> recovers to CLOSED
        breaker.record_success()
        self.assertEqual(breaker.state, CircuitState.CLOSED)
        self.assertEqual(breaker.failure_count, 0)

    async def test_database_auto_reconnect(self):
        """Test Database.get_connection automatically reconnects if connection was closed or invalidated."""
        from pokerparser.storage.database import Database

        db_path = os.path.join(self.temp_dir, "reconnect_test.db")
        db = Database(db_path=db_path)
        await db.init_db()

        conn1 = await db.get_connection()
        self.assertIsNotNone(conn1)

        # Forcefully close connection behind the scenes
        await conn1.close()

        # Next get_connection should detect closed connection and reconnect seamlessly
        conn2 = await db.get_connection()
        self.assertIsNotNone(conn2)
        async with conn2.execute("SELECT 1") as cursor:
            row = await cursor.fetchone()
            self.assertEqual(row[0], 1)

        await db.close()


if __name__ == "__main__":
    unittest.main()
