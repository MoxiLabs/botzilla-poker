import discord
from discord.ext import commands
from datetime import datetime, timedelta
from ..core import t, send_discord_message, config
from ..scraper_utils import fetch_freerolls, get_event_datetime, create_event_embed, GLOBAL_EVENTS

class PokerCommands(commands.Cog):
    """Cog for user-facing poker commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.command_suffix = config.get("command_suffix", "")

    @commands.command(name=f"day{config.get('command_suffix', '')}")
    async def cmd_day(self, ctx):
        events = GLOBAL_EVENTS if GLOBAL_EVENTS else await fetch_freerolls()
        now = datetime.now()
        
        # Events in the next 24 hours (now + 24 hours)
        next_24h_cutoff = now + timedelta(hours=24)
        next_24h = [e for e in events if now <= get_event_datetime(e) <= next_24h_cutoff]

        if not next_24h:
            await send_discord_message(ctx.channel, t("no_freerolls_24h"))
            return

        await send_discord_message(ctx.channel, content=t("freerolls_next_24h"))
        for e in next_24h:
            emb, attach = await create_event_embed(e)
            await send_discord_message(ctx.channel, embed=emb, file=attach)

    @commands.command(name=f"next{config.get('command_suffix', '')}")
    async def cmd_next(self, ctx):
        events = GLOBAL_EVENTS if GLOBAL_EVENTS else await fetch_freerolls()
        now = datetime.now()
        
        # Filter out all-day events and get future events
        future = [e for e in events if not e['is_all_day'] and get_event_datetime(e) > now]

        if not future:
            await send_discord_message(ctx.channel, t("no_upcoming_freeroll"))
            return

        nxt = future[0]
        delta = get_event_datetime(nxt) - now
        total_minutes = int(delta.total_seconds() / 60)
        
        time_msg = t("starts_in_minutes", min=total_minutes)
        emb, attach = await create_event_embed(nxt)
        await send_discord_message(ctx.channel, content=t("next_freeroll") + time_msg, embed=emb, file=attach)

    @commands.command(name=f"debug{config.get('command_suffix', '')}")
    async def cmd_debug(self, ctx):
        events = await fetch_freerolls()
        await send_discord_message(ctx.channel, t("debug_freerolls_loaded", count=len(events)))

    @commands.command(name=f"test{config.get('command_suffix', '')}")
    async def cmd_test(self, ctx):
        await send_discord_message(ctx.channel, t("test_ok"))

    @commands.command(name=f"help{config.get('command_suffix', '')}")
    async def cmd_help(self, ctx):
        suffix = self.command_suffix
        
        embed = discord.Embed(
            title=t("help_title"),
            description=t("help_description"),
            color=discord.Color.blue()
        )
        
        commands_list = [
            t("help_cmd_day", suffix=suffix),
            t("help_cmd_next", suffix=suffix),
            t("help_cmd_test", suffix=suffix),
            t("help_cmd_help", suffix=suffix)
        ]
        
        # We group commands under a 'Commands' header
        # Note: 'help_field_commands' isn't in JSON yet, using hardcoded localized or generic header
        embed.add_field(name="🛠️ Parancsok / Commands", value="\n".join(commands_list), inline=False)
        embed.add_field(name=t("help_notif_title"), value=t("help_notif_desc"), inline=False)
        embed.set_footer(text=t("help_footer"))
        
        await send_discord_message(ctx.channel, embed=embed)


async def setup(bot):
    await bot.add_cog(PokerCommands(bot))
