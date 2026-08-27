"""Broadcaster service handling tournament announcements and timed alerts to Discord."""

import asyncio
from typing import Optional, Union
import discord

from ..config.settings import Settings
from ..config.i18n import I18nService, default_i18n
from ..domain.models import Tournament
from ..services.alert_service import AlertService
from .ui.components import TournamentComponentBuilder
from .ui.views import FreerollPaginatorView
from ..events.bus import EventBus
from ..events.events import (
    NewTournamentsDiscoveredEvent,
    TournamentAlertTriggeredEvent,
)
from ..utils.logger import log


class DiscordBroadcaster:
    """Listens to domain events and broadcasts announcements/alerts to configured Discord channels."""

    def __init__(
        self,
        bot: discord.Client,
        settings: Settings,
        alert_service: AlertService,
        component_builder: TournamentComponentBuilder,
        event_bus: EventBus,
        i18n: Optional[I18nService] = None,
    ):
        self.bot = bot
        self.settings = settings
        self.alert_service = alert_service
        self.component_builder = component_builder
        self.event_bus = event_bus
        self.i18n = i18n or getattr(component_builder, "i18n", default_i18n)

        # Register event bus subscribers
        self._subscribe_events()

    def _subscribe_events(self):
        """Subscribes broadcaster methods to EventBus."""
        self.event_bus.subscribe(
            NewTournamentsDiscoveredEvent, self.on_new_tournaments_discovered
        )
        self.event_bus.subscribe(
            TournamentAlertTriggeredEvent, self.on_tournament_alert_triggered
        )

    async def on_new_tournaments_discovered(self, event: NewTournamentsDiscoveredEvent):
        """Handler: persist tournaments to DB and broadcast to Discord channel via Components V2."""
        # 1. Persist to DB in batch
        await self.alert_service.mark_events_sent(event.tournaments)

        # 2. Send to Discord
        if not self.settings.channel_id:
            return

        channel_obj = self.bot.get_channel(self.settings.channel_id)
        if not channel_obj:
            return

        # For daily summaries with multiple tournaments, send a single interactive paginator
        if event.is_daily_summary and len(event.tournaments) > 1:
            paginator = FreerollPaginatorView(
                tournaments=event.tournaments,
                component_builder=self.component_builder,
                i18n=self.i18n,
            )
            _, attach = await paginator.get_current_payload()
            await self.send_message(channel_obj, content=self.i18n("freerolls_next_24h"), view=paginator, file=attach)
        else:
            banner = self.i18n("new_daily_event") if not event.is_daily_summary else self.i18n("freerolls_next_24h")
            for i, tournament in enumerate(event.tournaments):
                if i > 0:
                    await asyncio.sleep(0.5)  # Rate-limit safety delay
                layout_view, attach = await self.component_builder.build_tournament_layout(
                    tournament, banner=banner
                )
                await self.send_message(channel_obj, view=layout_view, file=attach)
                banner = None

    async def on_tournament_alert_triggered(self, event: TournamentAlertTriggeredEvent):
        """Handler: send 1h warning or 10m urgent alert to Discord channel via Components V2."""
        if not self.settings.channel_id:
            return

        channel_obj = self.bot.get_channel(self.settings.channel_id)
        if not channel_obj:
            return

        is_urgent = event.alert_type == "urgent"
        msg_key = "urgent_starts_in_minutes" if is_urgent else "starts_in_minutes"
        banner = self.i18n(msg_key, min=event.minutes_left)

        layout_view, attach = await self.component_builder.build_tournament_layout(
            event.tournament, urgent=is_urgent, banner=banner
        )
        await self.send_message(channel_obj, view=layout_view, file=attach)

    async def send_message(
        self,
        target: discord.abc.Messageable,
        content: Optional[str] = None,
        file: Optional[discord.File] = None,
        view: Optional[Union[discord.ui.View, discord.ui.LayoutView]] = None,
        **extra_kwargs,
    ):
        """Unified message sender with support for DRY_RUN mode and Components V2."""
        if self.settings.dry_run:
            msg = f"[DRY_RUN] To {target}: {content if content else ''}"
            if file:
                msg += f" [File: {file.filename}]"
            if view:
                msg += f" [View: {view.__class__.__name__}]"
            log.info(msg)
            return

        kwargs = dict(extra_kwargs)
        if content is not None:
            kwargs["content"] = content
        if file is not None:
            kwargs["file"] = file
        if view is not None:
            kwargs["view"] = view

        try:
            await target.send(**kwargs)
        except discord.Forbidden as e:
            log.error(f"Permission denied sending Discord message to {target}: {e}")
        except discord.NotFound as e:
            log.error(f"Target channel or message {target} not found: {e}")
        except discord.HTTPException as e:
            log.error(f"Discord HTTP exception ({e.status}) sending to {target}: {e.text}")
        except Exception as e:
            log.error(f"Unexpected error sending Discord message to {target}: {e}", exc_info=True)
