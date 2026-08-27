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
        - !sync: Syncs to the current server (fast).
        - !sync global: Syncs globally (slow, up to 1 hour).
        - !sync copy: Copies global commands and syncs to this server.
        """
        if spec == "global":
            synced = await self.bot.tree.sync()
            await ctx.send(self.t("cmd_sync_global_done", count=len(synced)))
        elif spec == "copy":
            self.bot.tree.copy_global_to(guild=ctx.guild)
            synced = await self.bot.tree.sync(guild=ctx.guild)
            await ctx.send(self.t("cmd_sync_copy_done", count=len(synced)))
        else:
            synced = await self.bot.tree.sync(guild=ctx.guild)
            await ctx.send(self.t("cmd_sync_done", count=len(synced)))

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
        cog.sync_commands.aliases.append(f"sync{bot.settings.command_suffix}")
        cog.clear_commands.aliases.append(f"clear_commands{bot.settings.command_suffix}")
    await bot.add_cog(cog)
