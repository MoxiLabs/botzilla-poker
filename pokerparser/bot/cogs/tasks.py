"""Background tasks Cog for Botzilla (watcher and status rotator) using EventBus."""

from datetime import datetime
from itertools import cycle
from typing import TYPE_CHECKING
import discord
from discord.ext import commands, tasks

from ...events.events import (
    NewTournamentsDiscoveredEvent,
    TournamentAlertTriggeredEvent,
)
from ...utils.logger import log

if TYPE_CHECKING:
    from ..client import PokerBot


class PokerTasks(commands.Cog):
    """Cog managing background loops for tournament monitoring and status rotation."""

    def __init__(self, bot: "PokerBot"):
        self.bot = bot

        # Status messages rotator
        status_msgs = bot.i18n.translate("status_messages")
        if not isinstance(status_msgs, list):
            status_msgs = bot.settings.status_messages or [
                "Monitoring freerolls…",
                "Hunt is on…",
                "Botzilla in active mode",
                "10-minute alerts ready",
                "New freeroll approaching…",
            ]
        self.status_messages = cycle(status_msgs)

        # Dynamic loop intervals from settings
        self.status_rotator.change_interval(seconds=bot.settings.status_rotator_sleep_seconds)
        self.watcher.change_interval(seconds=bot.settings.watcher_sleep_seconds)

        # Start loops
        self.status_rotator.start()
        self.watcher.start()

    def cog_unload(self):
        self.status_rotator.cancel()
        self.watcher.cancel()

    @tasks.loop(seconds=20)
    async def status_rotator(self):
        """Cycle through status messages in bot presence."""
        if not self.bot.is_ready():
            return
        current_status = next(self.status_messages)
        await self.bot.change_presence(activity=discord.Game(name=current_status))

    @tasks.loop(seconds=300)
    async def watcher(self):
        """Periodic watcher loop: publishes domain events on tournament discoveries and alerts."""
        if not self.bot.is_ready():
            return

        now = datetime.now()
        today = now.date()

        # 1. Fetch latest tournaments and cleanup old DB entries
        events = await self.bot.tournament_service.fetch_tournaments()
        await self.bot.alert_service.cleanup(today=today, current_time=now)

        # 2. Filter events in the next 24 hours
        next_24h = await self.bot.tournament_service.get_upcoming_tournaments(hours=24)

        # 3. Discover new daily events -> Publish Event
        unnotified = await self.bot.alert_service.get_unnotified_events(next_24h)
        if unnotified:
            already_sent_today = await self.bot.alert_service.has_sent_today(today)
            is_daily_summary = not already_sent_today

            await self.bot.event_bus.publish(
                NewTournamentsDiscoveredEvent(
                    tournaments=unnotified,
                    is_daily_summary=is_daily_summary,
                )
            )

        # 4. Check Timed Alerts -> Publish Events
        due_alerts = self.bot.alert_service.get_due_timed_alerts(next_24h, now=now)
        for event, alert_type, minutes_left in due_alerts:
            self.bot.alert_service.mark_timed_alert_sent(event, alert_type)
            await self.bot.event_bus.publish(
                TournamentAlertTriggeredEvent(
                    tournament=event,
                    alert_type=alert_type,
                    minutes_left=minutes_left,
                )
            )

    @watcher.before_loop
    @status_rotator.before_loop
    async def before_poker_loops(self):
        await self.bot.wait_until_ready()

    @watcher.error
    async def on_watcher_error(self, error: Exception):
        """Catches and logs any unhandled exceptions in the watcher loop."""
        log.error(f"Unhandled error in PokerTasks.watcher loop: {error}", exc_info=True)

    @status_rotator.error
    async def on_status_rotator_error(self, error: Exception):
        """Catches and logs any unhandled exceptions in the status rotator loop."""
        log.error(f"Unhandled error in PokerTasks.status_rotator loop: {error}", exc_info=True)


async def setup(bot: "PokerBot"):
    await bot.add_cog(PokerTasks(bot))
