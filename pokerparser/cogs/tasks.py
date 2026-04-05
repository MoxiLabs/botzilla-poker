import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from itertools import cycle
from typing import List, cast, Union, Optional

from ..core import config, t, send_discord_message, log
from ..scraper_utils import fetch_freerolls, get_event_datetime, create_event_embed, GLOBAL_EVENTS
from ..database import is_event_sent, add_sent_event, has_sent_today, cleanup_old_events

class PokerTasks(commands.Cog):
    """Cog for background poker tasks (watcher, status rotator)"""

    def __init__(self, bot):
        self.bot = bot
        self.channel_id = config.get("channel_id")
        
        # In-memory alert tracking (last 2 hours)
        self.sent_alerts = set()
        
        # Status rotator iterator
        status_msgs = config.get("status_messages", [
            "👹 Monitoring freerolls…",
            "🃏 Hunt is on…",
            "💰 Botzilla in active mode",
            "🧨 10-minute alerts ready",
            "♠️ New freeroll approaching…"
        ])
        # Try to get from translations if available
        # TRANSLATIONS might not be directly accessible here easily, let's just stick to config or defaults
        self.status_messages = cycle(status_msgs)
        
        # Start the loops
        self.status_rotator.start()
        self.watcher.start()

    def cog_unload(self):
        self.status_rotator.cancel()
        self.watcher.cancel()

    @tasks.loop(seconds=20)
    async def status_rotator(self):
        """Cycle through status messages in the bot's presence"""
        if not self.bot.is_ready():
            return
            
        current_status = next(self.status_messages)
        # We try to use translations if we can find them, but for now we'll stick to config/default
        await self.bot.change_presence(activity=discord.Game(name=current_status))

    @tasks.loop(seconds=300)
    async def watcher(self):
        """Main check loop: Daily summary and timed alerts"""
        if not self.bot.is_ready():
            return

        channel_obj = self.bot.get_channel(self.channel_id)
        if not channel_obj:
            log.error(f"Channel with ID {self.channel_id} not found")
            return

        channel = cast(Union[discord.TextChannel, discord.Thread], channel_obj)
        
        # Fetch new events
        events = await fetch_freerolls()
        now = datetime.now()
        today = now.date()

        # Cleanup: remove old DB records
        await cleanup_old_events(today)
        
        # Events in the next 24 hours
        next_24h_cutoff = now + timedelta(hours=24)
        next_24h = [e for e in events if now <= get_event_datetime(e) <= next_24h_cutoff]
        
        # 1. New daily event check
        new_events = []
        for e in next_24h:
            if not await is_event_sent(e):
                new_events.append(e)
        
        if new_events:
            if await has_sent_today(today):
                await send_discord_message(channel, content=t("new_daily_event"))
            else:
                await send_discord_message(channel, content=t("freerolls_next_24h"))
            
            for e in new_events:
                emb, attach = await create_event_embed(e)
                await send_discord_message(channel, embed=emb, file=attach)
                await add_sent_event(e)

        # 2. Timed Alerts (1h and 10min)
        next_24h_timed = [e for e in events if not e['is_all_day'] and now <= get_event_datetime(e) <= next_24h_cutoff]
        
        thresholds = config.get("alert_thresholds", {"warning": 60, "urgent": 10})
        warning_min = thresholds.get("warning", 60)
        urgent_min = thresholds.get("urgent", 10)
        
        for nxt in next_24h_timed:
            delta = get_event_datetime(nxt) - now
            total_minutes = int(delta.total_seconds() / 60)

            # Warning alert
            if total_minutes < warning_min and total_minutes > urgent_min:
                event_key = (get_event_datetime(nxt), nxt["name"], 'warning')
                if event_key not in self.sent_alerts:
                    self.sent_alerts.add(event_key)
                    emb, attach = await create_event_embed(nxt)
                    await send_discord_message(
                        channel,
                        content=t("starts_in_minutes", min=total_minutes),
                        embed=emb,
                        file=attach
                    )

            # Urgent alert
            if total_minutes < urgent_min and total_minutes >= 0:
                event_key = (get_event_datetime(nxt), nxt["name"], 'urgent')
                if event_key not in self.sent_alerts:
                    self.sent_alerts.add(event_key)
                    emb, attach = await create_event_embed(nxt, urgent=True)
                    await send_discord_message(
                        channel,
                        content=t("urgent_starts_in_minutes", min=total_minutes),
                        embed=emb,
                        file=attach
                    )

        # Cleanup in-memory alerts (older than 2 hours)
        cutoff_time = now - timedelta(hours=2)
        self.sent_alerts = {
            (dt, name, alert_type) for (dt, name, alert_type) in self.sent_alerts 
            if dt > cutoff_time
        }

    @watcher.before_loop
    @status_rotator.before_loop
    async def before_poker_loops(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(PokerTasks(bot))
