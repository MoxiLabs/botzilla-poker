from discord.ext import commands
from discord import app_commands
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
        await self._day_logic(ctx)

    @app_commands.command(name="day", description="Shows freerolls for the next 24 hours")
    async def slash_day(self, interaction: discord.Interaction):
        await self._day_logic(interaction)

    async def _day_logic(self, source):
        events = GLOBAL_EVENTS if GLOBAL_EVENTS else await fetch_freerolls()
        now = datetime.now()
        
        # Events in the next 24 hours (now + 24 hours)
        next_24h_cutoff = now + timedelta(hours=24)
        next_24h = [e for e in events if now <= get_event_datetime(e) <= next_24h_cutoff]

        # Get target for message sending
        target = source.channel if hasattr(source, "channel") else source.channel

        if not next_24h:
            await send_discord_message(target, t("no_freerolls_24h"))
            return

        # Prepare first response
        if isinstance(source, discord.Interaction):
            await source.response.send_message(content=t("freerolls_next_24h"))
        else:
            await send_discord_message(target, content=t("freerolls_next_24h"))
            
        for e in next_24h:
            emb, attach, view = await create_event_embed(e)
            await send_discord_message(target, embed=emb, file=attach, view=view)

    @commands.command(name=f"next{config.get('command_suffix', '')}")
    async def cmd_next(self, ctx):
        await self._next_logic(ctx)

    @app_commands.command(name="next", description="Shows the very next upcoming freeroll")
    async def slash_next(self, interaction: discord.Interaction):
        await self._next_logic(interaction)

    async def _next_logic(self, source):
        events = GLOBAL_EVENTS if GLOBAL_EVENTS else await fetch_freerolls()
        now = datetime.now()
        
        # Filter out all-day events and get future events
        future = [e for e in events if not e['is_all_day'] and get_event_datetime(e) > now]

        target = source.channel if hasattr(source, "channel") else source.channel

        if not future:
            await send_discord_message(target, t("no_upcoming_freeroll"))
            return

        nxt = future[0]
        delta = get_event_datetime(nxt) - now
        total_minutes = int(delta.total_seconds() / 60)
        
        time_msg = t("starts_in_minutes", min=total_minutes)
        emb, attach, view = await create_event_embed(nxt)
        
        content = t("next_freeroll") + time_msg
        if isinstance(source, discord.Interaction):
            await source.response.send_message(content=content, embed=emb, file=attach, view=view)
        else:
            await send_discord_message(target, content=content, embed=emb, file=attach, view=view)

    @commands.command(name=f"debug{config.get('command_suffix', '')}")
    async def cmd_debug(self, ctx):
        await self._debug_logic(ctx)

    @app_commands.command(name="debug", description="Shows technical info about loaded freerolls")
    async def slash_debug(self, interaction: discord.Interaction):
        await self._debug_logic(interaction)

    async def _debug_logic(self, source):
        events = await fetch_freerolls()
        target = source.channel if hasattr(source, "channel") else source.channel
        content = t("debug_freerolls_loaded", count=len(events))
        if isinstance(source, discord.Interaction):
             await source.response.send_message(content=content, ephemeral=True)
        else:
            await send_discord_message(target, content)

    @commands.command(name=f"test{config.get('command_suffix', '')}")
    async def cmd_test(self, ctx):
        await self._test_logic(ctx)

    @app_commands.command(name="test", description="Pings the bot to check if it is alive")
    async def slash_test(self, interaction: discord.Interaction):
        await self._test_logic(interaction)

    async def _test_logic(self, source):
        target = source.channel if hasattr(source, "channel") else source.channel
        content = t("test_ok")
        if isinstance(source, discord.Interaction):
             await source.response.send_message(content=content)
        else:
            await send_discord_message(target, content)

    @commands.command(name=f"help{config.get('command_suffix', '')}")
    async def cmd_help(self, ctx):
        await self._help_logic(ctx)

    @app_commands.command(name="help", description="Shows the poker bot's instruction manual")
    async def slash_help(self, interaction: discord.Interaction):
        await self._help_logic(interaction)

    async def _help_logic(self, source):
        suffix = self.command_suffix
        target = source.channel if hasattr(source, "channel") else source.channel
        
        # Premium Deep Blue Color
        COLOR_HELP = 0x2980b9
        
        embed = discord.Embed(
            title=f"🃏 {t('help_title')}",
            description=t("help_description"),
            color=COLOR_HELP
        )
        
        # Set bot avatar as thumbnail for premium look
        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)
        
        # 1. Slash Commands Section (Modern)
        slash_list = [
            f"🚀 `/day` - {t('help_slash_day')}",
            f"🎯 `/next` - {t('help_slash_next')}",
            f"ℹ️ `/help` - {t('help_slash_help')}"
        ]
        embed.add_field(name=f"✨ {t('help_header_slash')}", value="\n".join(slash_list), inline=False)

        # 2. Legacy Prefix Commands Section
        prefix_list = [
            t("help_cmd_day", suffix=suffix),
            t("help_cmd_next", suffix=suffix),
            t("help_cmd_help", suffix=suffix)
        ]
        embed.add_field(name=f"🛠️ {t('help_header_prefix')}", value="\n".join(prefix_list), inline=False)
        
        # 3. Notification Info
        embed.add_field(name=f"📢 {t('help_notif_title')}", value=t("help_notif_desc"), inline=False)
        
        embed.set_footer(text=f"Botzilla Poker • {t('help_footer')}")
        
        if isinstance(source, discord.Interaction):
             await source.response.send_message(embed=embed)
        else:
            await send_discord_message(target, embed=embed)


async def setup(bot):
    await bot.add_cog(PokerCommands(bot))
