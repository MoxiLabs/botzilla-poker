"""Application Inversion of Control (IoC) Dependency Injection Container."""

from typing import List, Optional, Sequence
import discord

from .config.settings import Settings, get_settings
from .config.i18n import I18nService
from .domain.models import Tournament
from .events.bus import EventBus
from .storage.database import Database
from .storage.repository import EventRepository
from .scrapers.base import BaseScraper
from .scrapers.manager import ScraperManager, create_default_scrapers
from .services.tournament_service import TournamentService
from .services.alert_service import AlertService
from .bot.ui.assets import AssetManager
from .bot.ui.components import TournamentComponentBuilder
from .bot.broadcaster import DiscordBroadcaster
from .bot.client import PokerBot
from .utils.logger import setup_logger, setup_discord_logging


class AppContainer:
    """
    Centralized Application IoC Container.
    Manages dependency graph, singleton lifecycles, and allows clean testing overrides.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        i18n: Optional[I18nService] = None,
        database: Optional[Database] = None,
        repository: Optional[EventRepository] = None,
        scrapers: Optional[Sequence[BaseScraper]] = None,
        scraper_manager: Optional[ScraperManager] = None,
        tournament_service: Optional[TournamentService] = None,
        alert_service: Optional[AlertService] = None,
        asset_manager: Optional[AssetManager] = None,
        component_builder: Optional[TournamentComponentBuilder] = None,
        event_bus: Optional[EventBus] = None,
        broadcaster: Optional[DiscordBroadcaster] = None,
        bot: Optional[PokerBot] = None,
        setup_loggers: bool = True,
    ):
        # 1. Settings & Configuration
        self.settings: Settings = settings or get_settings()

        # 2. Logging Setup
        if setup_loggers:
            setup_logger(
                log_file=self.settings.logging.file,
                max_bytes=self.settings.logging.max_bytes,
                backup_count=self.settings.logging.backup_count,
            )
            setup_discord_logging(
                log_file=self.settings.logging.file,
                max_bytes=self.settings.logging.max_bytes,
                backup_count=self.settings.logging.backup_count,
            )

        # 3. Localization Service (Config-driven with fallback)
        self.i18n: I18nService = i18n or I18nService(
            locale=self.settings.locale,
            fallback_locale="en",
        )

        # 4. Storage & Persistence Layer
        self.database: Database = database or Database(db_path=self.settings.db_file)
        self.repository: EventRepository = repository or EventRepository(database=self.database)

        # 5. Scrapers & Scraper Manager
        if scraper_manager is not None:
            self.scraper_manager = scraper_manager
            self.scrapers = list(self.scraper_manager.scrapers)
        else:
            self.scrapers = list(scrapers) if scrapers is not None else create_default_scrapers(
                url_password=self.settings.url_password,
                url_pass=self.settings.url_pass,
                timezone=self.settings.timezone,
            )
            self.scraper_manager = ScraperManager(scrapers=self.scrapers)

        # 6. Domain Services Layer
        self.tournament_service: TournamentService = tournament_service or TournamentService(
            scraper_manager=self.scraper_manager
        )
        self.alert_service: AlertService = alert_service or AlertService(
            repository=self.repository,
            thresholds=self.settings.alert_thresholds,
        )

        # 7. UI & Asset Management Layer
        self.asset_manager: AssetManager = asset_manager or AssetManager()
        self.component_builder: TournamentComponentBuilder = component_builder or TournamentComponentBuilder(
            asset_manager=self.asset_manager,
            i18n=self.i18n,
            high_value_threshold=self.settings.high_value_threshold,
            timezone=self.settings.timezone,
            command_prefix=self.settings.command_prefix,
            command_suffix=self.settings.command_suffix,
        )

        # 8. Event-Driven Messaging Bus
        self.event_bus: EventBus = event_bus or EventBus()

        # 9. Discord Bot & Broadcaster Integration
        if bot is not None:
            self.bot = bot
            self.broadcaster = broadcaster or self.bot.broadcaster
        else:
            self.bot = self._create_bot_instance(broadcaster=broadcaster)
            self.broadcaster = self.bot.broadcaster

    def _create_bot_instance(self, broadcaster: Optional[DiscordBroadcaster] = None) -> PokerBot:
        """Constructs and configures PokerBot with DI container dependencies."""
        intents = discord.Intents.default()
        intents.message_content = True

        bot = PokerBot(
            settings=self.settings,
            i18n=self.i18n,
            database=self.database,
            repository=self.repository,
            tournament_service=self.tournament_service,
            alert_service=self.alert_service,
            component_builder=self.component_builder,
            event_bus=self.event_bus,
            broadcaster=broadcaster,
            intents=intents,
        )

        # Global channel restriction check
        @bot.check
        async def channel_restriction_check(ctx) -> bool:
            if not self.settings.allowed_channel_ids:
                return True
            return ctx.channel.id in self.settings.allowed_channel_ids

        # Global Slash Command error handler
        @bot.tree.error
        async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
            if isinstance(error, discord.app_commands.CommandOnCooldown):
                msg = self.i18n.translate("error_cooldown", retry_after=f"{error.retry_after:.1f}")
            elif isinstance(error, (discord.app_commands.MissingPermissions, discord.app_commands.CheckFailure)):
                msg = self.i18n.translate("error_channel_restricted")
            else:
                from .utils.logger import log
                log.error(f"Unhandled slash command error on '{interaction.command}': {error}", exc_info=error)
                msg = self.i18n.translate("error_generic")

            if not interaction.response.is_done():
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                await interaction.followup.send(msg, ephemeral=True)

        return bot
