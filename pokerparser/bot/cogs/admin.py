"""Administrative commands Cog for Botzilla."""

from typing import Optional, TYPE_CHECKING
import discord
from discord.ext import commands

if TYPE_CHECKING:
    from ..client import PokerBot


class AdminCommands(commands.Cog):
    """Administrative commands for bot maintenance and command syncing."""

    def __init__(self, bot: "PokerBot"):
        self.bot = bot
        self.command_suffix = bot.settings.command_suffix

    def t(self, key: str, **kwargs):
        """Helper to translate using bot's injected i18n service."""
        return self.bot.i18n.translate(key, **kwargs)

    @commands.command(name="sync")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def sync_commands(self, ctx: commands.Context, spec: Optional[str] = None):
        """
        Refreshes/Syncs slash commands to Discord.
        - !sync / !sync_poker: Syncs to this server AND globally.
        - !sync global: Syncs globally (slow, up to 1 hour).
        """
        from ...utils.logger import log

        global_cmds = self.bot.tree.get_commands()
        log.info(f"Sync invoked by {ctx.author}. Tree has {len(global_cmds)} global commands: {[c.name for c in global_cmds]}")

        if spec == "global":
            synced = await self.bot.tree.sync()
            log.info(f"Synced {len(synced)} global commands")
            await ctx.send(self.t("cmd_sync_global_done", count=len(synced)))
            return

        # 1. Copy to current guild and sync
        self.bot.tree.copy_global_to(guild=ctx.guild)
        synced_guild = await self.bot.tree.sync(guild=ctx.guild)
        log.info(f"Synced {len(synced_guild)} guild commands to {ctx.guild.name} ({ctx.guild.id})")

        # 2. Also sync globally as fallback
        synced_global = await self.bot.tree.sync()
        log.info(f"Also synced {len(synced_global)} global commands")

        count = len(synced_guild) if len(synced_guild) > 0 else len(synced_global)
        await ctx.send(self.t("cmd_sync_done", count=count))

    @commands.command(name="clear_commands")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def clear_commands(self, ctx: commands.Context):
        """Deletes all slash commands associated with the bot from Discord."""
        # Global clear
        self.bot.tree.clear_commands(guild=None)
        await self.bot.tree.sync(guild=None)

        # Guild clear
        self.bot.tree.clear_commands(guild=ctx.guild)
        await self.bot.tree.sync(guild=ctx.guild)

        prefix = self.bot.settings.command_prefix
        sync_cmd = f"{prefix}sync{self.command_suffix}"
        await ctx.send(self.t("cmd_clear_done", cmd=sync_cmd))


async def setup(bot: "PokerBot"):
    cog = AdminCommands(bot)
    if bot.settings.command_suffix:
        alias_sync = f"sync{bot.settings.command_suffix}"
        if alias_sync not in cog.sync_commands.aliases:
            cog.sync_commands.aliases.append(alias_sync)
        alias_clear = f"clear_commands{bot.settings.command_suffix}"
        if alias_clear not in cog.clear_commands.aliases:
            cog.clear_commands.aliases.append(alias_clear)
    await bot.add_cog(cog)
