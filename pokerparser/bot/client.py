"""Discord Bot client initialization and dependency wiring."""

import os
import sys
from typing import Optional, Union
import aiohttp
import discord
from discord.ext import commands

from ..config.settings import Settings, get_settings
from ..config.i18n import I18nService
from ..storage.database import Database
from ..storage.repository import EventRepository
from ..services.tournament_service import TournamentService
from ..services.alert_service import AlertService
from .ui.components import TournamentComponentBuilder
from .broadcaster import DiscordBroadcaster
from ..events.bus import EventBus
from ..utils.logger import log


class PokerBot(commands.Bot):
    """Custom Discord bot with injected domain, UI, and broadcaster services."""

    def __init__(
        self,
        settings: Settings,
        i18n: I18nService,
        database: Database,
        repository: EventRepository,
        tournament_service: TournamentService,
        alert_service: AlertService,
        component_builder: Optional[TournamentComponentBuilder] = None,
        event_bus: Optional[EventBus] = None,
        broadcaster: Optional[DiscordBroadcaster] = None,
        **bot_kwargs,
    ):
        super().__init__(
            command_prefix=settings.command_prefix,
            help_command=None,
            **bot_kwargs,
        )
        self.settings = settings
        self.i18n = i18n
        self.database = database
        self.repository = repository
        self.tournament_service = tournament_service
        self.alert_service = alert_service
        self.component_builder = component_builder or TournamentComponentBuilder(
            high_value_threshold=settings.high_value_threshold,
            timezone=settings.timezone,
            command_prefix=settings.command_prefix,
            command_suffix=settings.command_suffix,
        )
        self.event_bus = event_bus or EventBus()
        self.broadcaster = broadcaster or DiscordBroadcaster(
            bot=self,
            settings=settings,
            alert_service=alert_service,
            component_builder=self.component_builder,
            event_bus=self.event_bus,
            i18n=self.i18n,
        )
        self.http_session: Optional[aiohttp.ClientSession] = None

    async def setup_hook(self):
        """Called automatically before the bot connects to Discord."""
        # 1. Initialize persistent aiohttp ClientSession
        self.http_session = aiohttp.ClientSession()
        self.tournament_service.set_session(self.http_session)
        self.component_builder.asset_manager.session = self.http_session

        # 2. Initialize SQLite tables
        await self.database.init_db()

        # 3. Load Cogs
        extensions = [
            "pokerparser.bot.cogs.admin",
            "pokerparser.bot.cogs.commands",
            "pokerparser.bot.cogs.tasks",
        ]
        for ext in extensions:
            try:
                await self.load_extension(ext)
                log.info(f"Loaded extension: {ext}")
            except Exception as e:
                log.error(f"Failed to load extension {ext}: {e}")

    async def close(self):
        """Gracefully close bot connections, persistent database, and the shared aiohttp ClientSession."""
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
            log.info("Closed shared aiohttp ClientSession.")
        await self.database.close()
        await super().close()

    async def on_command_error(self, ctx: commands.Context, error: Exception):
        """Global handler for prefix and hybrid command errors."""
        # Unwrap CommandInvokeError
        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        if isinstance(error, commands.CommandOnCooldown):
            msg = self.i18n.translate("error_cooldown", retry_after=f"{error.retry_after:.1f}")
            await ctx.send(msg, ephemeral=True)
            return

        if isinstance(error, (commands.MissingPermissions, commands.NotOwner)):
            msg = self.i18n.translate("error_no_permission")
            await ctx.send(msg, ephemeral=True)
            return

        if isinstance(error, commands.CheckFailure):
            msg = self.i18n.translate("error_channel_restricted")
            await ctx.send(msg, ephemeral=True)
            return

        if isinstance(error, commands.CommandNotFound):
            return

        log.error(f"Unhandled error in command '{ctx.command}': {error}", exc_info=error)
        await ctx.send(self.i18n.translate("error_generic"), ephemeral=True)

    async def send_message(
        self,
        target: discord.abc.Messageable,
        content: Optional[str] = None,
        file: Optional[discord.File] = None,
        view: Optional[Union[discord.ui.View, discord.ui.LayoutView]] = None,
        **extra_kwargs,
    ):
        """Unified message sender forwarded to DiscordBroadcaster."""
        await self.broadcaster.send_message(
            target=target, content=content, file=file, view=view, **extra_kwargs
        )


def create_bot(settings: Optional[Settings] = None, **container_overrides) -> PokerBot:
    """Factory creating a fully wired PokerBot instance via IoC AppContainer."""
    from ..container import AppContainer

    container = AppContainer(settings=settings, **container_overrides)
    return container.bot


def run_bot(settings: Optional[Settings] = None):
    """Main execution function to run the bot."""
    cfg = settings or get_settings()

    if not cfg.discord_token:
        print("ERROR: DISCORD_TOKEN not found in environment or config.json", file=sys.stderr)
        sys.exit(1)

    bot = create_bot(cfg)
    try:
        log.info("Starting Discord bot...")
        bot.run(cfg.discord_token)
    except KeyboardInterrupt:
        log.info("Bot stopped by user.")
        sys.exit(0)
    except Exception as e:
        log.error(f"Error starting bot: {e}")
        sys.exit(1)
