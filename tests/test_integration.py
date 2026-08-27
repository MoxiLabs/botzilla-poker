"""End-to-End Integration tests with real in-process HTTP server and full pipeline."""

import asyncio
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
import aiohttp
from aiohttp import web
from aiohttp.test_utils import RawTestServer

from pokerparser.config.settings import Settings
from pokerparser.config.i18n import I18nService
from pokerparser.container import AppContainer
from pokerparser.scrapers.network.http_client import HttpFetcher
from pokerparser.scrapers.freeroll_password import FreeRollPasswordScraper
from pokerparser.scrapers.freerollpass import FreerollPassScraper
from pokerparser.events.events import NewTournamentsDiscoveredEvent, TournamentAlertTriggeredEvent
from pokerparser.bot.ui.views import FreerollPaginatorView


SAMPLE_FPW_HTML = """
<div class="pt-cv-wrapper">
    <div class="pt-cv-content-item">
        <a href="/tournaments/live-integration-1">
            <span class="exname">Live Stream Freeroll $500</span>
        </a>
        <div class="fpexcerpt">
            <span class="exroom"></span> GGPoker
            <span class="date-display-single">August 28, 2026</span>
            <span class="extime"></span> 20:00 GMT+2
            <span class="exprize"></span> $500
            <span class="exname"></span> Live Stream Freeroll $500
            <span class="expass2"> live_secret_888 </span>
        </div>
    </div>
</div>
"""

SAMPLE_PASS_HTML = """
<ul id="freerollList">
    <li class="row">
        <div class="col-4">
            <div class="f-size-30-576-40">18:00</div>
            <div class="f-size-15-576-20">28.08.2026</div>
            <div class="c-yellow">$1,000 GTD</div>
        </div>
        <div class="col-8">
            <div class="title-room">
                <a href="/rooms/pokerstars">PokerStars</a>
            </div>
            <a href="/freeroll/stars-live">
                <span class="fl-text-name">Stars Real Integration Event</span>
            </a>
            <div id="pwd-live">
                Password: <strong class="c-red-1">stars_pw_live</strong>
            </div>
        </div>
    </li>
</ul>
"""


class TestIntegrationPipeline(unittest.IsolatedAsyncioTestCase):
    """Integration test suite using in-process HTTP web server and end-to-end container pipeline."""

    async def asyncSetUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "integration_test.db")

        # 1. Setup local aiohttp server for mock HTTP requests
        self.app = web.Application()
        self.app.router.add_get("/fpw", self._handle_fpw)
        self.app.router.add_get("/pass", self._handle_pass)
        self.app.router.add_get("/storage/app/media/logo/pokerstars-x2.png", self._handle_logo)

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await self.site.start()

        port = self.site._server.sockets[0].getsockname()[1]
        self.url_fpw = f"http://127.0.0.1:{port}/fpw"
        self.url_pass = f"http://127.0.0.1:{port}/pass"

    async def asyncTearDown(self):
        await self.runner.cleanup()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def _handle_fpw(self, request):
        return web.Response(text=SAMPLE_FPW_HTML, content_type="text/html")

    async def _handle_pass(self, request):
        return web.Response(text=SAMPLE_PASS_HTML, content_type="text/html")

    async def _handle_logo(self, request):
        return web.Response(body=b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRDUMMY", content_type="image/png")

    async def test_real_http_scrapers_and_parsers(self):
        """Test real HTTP network requests against running HTTP server with parsers."""
        async with aiohttp.ClientSession() as session:
            fetcher = HttpFetcher(session=session)

            # Test real HTTP GET with HttpFetcher
            html_fpw = await fetcher.fetch_text(self.url_fpw)
            self.assertIn("Live Stream Freeroll", html_fpw)

            # Scraper integration
            scraper_fpw = FreeRollPasswordScraper(url=self.url_fpw, fetcher=fetcher)
            tourneys_fpw = await scraper_fpw.get_tournaments()
            self.assertEqual(len(tourneys_fpw), 1)
            self.assertEqual(tourneys_fpw[0].name, "Live Stream Freeroll $500")
            self.assertEqual(tourneys_fpw[0].password, "live_secret_888")

            scraper_pass = FreerollPassScraper(url=self.url_pass, fetcher=fetcher)
            tourneys_pass = await scraper_pass.get_tournaments()
            self.assertEqual(len(tourneys_pass), 1)
            self.assertEqual(tourneys_pass[0].name, "Stars Real Integration Event")
            self.assertEqual(tourneys_pass[0].room.name, "PokerStars")

    async def test_end_to_end_container_pipeline(self):
        """Test full end-to-end pipeline: Fetch -> Merge -> DB Persist -> EventBus -> Broadcaster."""
        settings = Settings(
            discord_token="dummy_integration_token",
            channel_id=999888777,
            url_password=self.url_fpw,
            url_pass=self.url_pass,
            dry_run=False,
            db_file=self.db_path,
        )

        container = AppContainer(settings=settings, setup_loggers=False)

        # Mock discord channel target
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()
        container.bot.get_channel = MagicMock(return_value=mock_channel)

        async with aiohttp.ClientSession() as session:
            container.tournament_service.set_session(session)
            container.asset_manager.session = session
            await container.database.init_db()

            # 1. Fetch tournaments from real mock HTTP endpoints
            tournaments = await container.tournament_service.fetch_tournaments()
            self.assertEqual(len(tournaments), 2)

            # 2. Check unnotified events
            unnotified = await container.alert_service.get_unnotified_events(tournaments)
            self.assertEqual(len(unnotified), 2)

            # 3. Publish NewTournamentsDiscoveredEvent through EventBus
            event = NewTournamentsDiscoveredEvent(tournaments=unnotified, is_daily_summary=True)
            await container.event_bus.publish(event)

            # 4. Verify broadcaster sent interactive message with FreerollPaginatorView
            mock_channel.send.assert_called_once()
            call_kwargs = mock_channel.send.call_args[1]
            self.assertIn("view", call_kwargs)
            self.assertIsInstance(call_kwargs["view"], FreerollPaginatorView)

            # 5. Verify database recorded events as sent
            remaining_unnotified = await container.alert_service.get_unnotified_events(tournaments)
            self.assertEqual(len(remaining_unnotified), 0)

            await container.database.close()


if __name__ == "__main__":
    unittest.main()
