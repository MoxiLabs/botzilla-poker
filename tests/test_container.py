"""Unit tests for Application IoC Container (AppContainer)."""

import os
import shutil
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock

from pokerparser.config.settings import Settings
from pokerparser.config.i18n import I18nService
from pokerparser.container import AppContainer
from pokerparser.storage.database import Database
from pokerparser.storage.repository import EventRepository
from pokerparser.scrapers.manager import ScraperManager
from pokerparser.services.tournament_service import TournamentService
from pokerparser.services.alert_service import AlertService
from pokerparser.events.bus import EventBus
from pokerparser.bot.client import PokerBot


class TestAppContainer(unittest.TestCase):
    """Test suite verifying IoC container wiring and overrides."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_container.db")
        self.settings = Settings(
            discord_token="test_token",
            dry_run=True,
            locale="en",
            db_file=self.db_path,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_default_container_wiring(self):
        """Test that AppContainer wires all dependencies correctly from settings."""
        container = AppContainer(settings=self.settings, setup_loggers=False)

        self.assertIs(container.settings, self.settings)
        self.assertEqual(container.i18n.locale, "en")
        self.assertIsInstance(container.database, Database)
        self.assertIsInstance(container.repository, EventRepository)
        self.assertIsInstance(container.scraper_manager, ScraperManager)
        self.assertIsInstance(container.tournament_service, TournamentService)
        self.assertIsInstance(container.alert_service, AlertService)
        self.assertIsInstance(container.event_bus, EventBus)
        self.assertIsInstance(container.bot, PokerBot)

        # Verify dependency injection into bot and broadcaster
        self.assertIs(container.bot.i18n, container.i18n)
        self.assertIs(container.bot.tournament_service, container.tournament_service)
        self.assertIs(container.bot.alert_service, container.alert_service)
        self.assertIs(container.bot.component_builder.i18n, container.i18n)
        self.assertIs(container.broadcaster.i18n, container.i18n)

    def test_container_dependency_overrides(self):
        """Test overriding dependencies (mocks/custom implementations) in AppContainer."""
        mock_db = MagicMock(spec=Database)
        mock_repo = MagicMock(spec=EventRepository)
        mock_bus = MagicMock(spec=EventBus)
        custom_i18n = I18nService(locale="hu")

        container = AppContainer(
            settings=self.settings,
            i18n=custom_i18n,
            database=mock_db,
            repository=mock_repo,
            event_bus=mock_bus,
            setup_loggers=False,
        )

        self.assertIs(container.i18n, custom_i18n)
        self.assertIs(container.database, mock_db)
        self.assertIs(container.repository, mock_repo)
        self.assertIs(container.event_bus, mock_bus)
        self.assertIs(container.alert_service.repository, mock_repo)
        self.assertIs(container.bot.event_bus, mock_bus)
        self.assertEqual(container.bot.i18n.locale, "hu")

    def test_settings_env_overrides(self):
        """Test DB_FILE, LOG_FILE, and LOG_LEVEL environment variable overrides."""
        from pokerparser.config.settings import get_settings
        import unittest.mock
        with unittest.mock.patch.dict(
            os.environ,
            {
                "DB_FILE": "/custom/path/custom.db",
                "LOG_FILE": "/custom/path/custom.log",
                "LOG_LEVEL": "DEBUG",
            },
        ):
            st = get_settings()
            self.assertEqual(st.db_file, "/custom/path/custom.db")
            self.assertEqual(st.logging.file, "/custom/path/custom.log")
            self.assertEqual(st.logging.level, "DEBUG")


if __name__ == "__main__":
    unittest.main()
