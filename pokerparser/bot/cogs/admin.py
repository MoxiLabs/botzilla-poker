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

    async def _ensure_commands_loaded(self):
        """Ensures in-memory command tree is fully populated from cogs."""
        from ...utils.logger import log
        if not self.bot.tree.get_commands():
            try:
                await self.bot.reload_extension("pokerparser.bot.cogs.commands")
                log.info(f"Reloaded commands cog. Tree commands: {[c.name for c in self.bot.tree.get_commands()]}")
            except Exception as e:
                log.error(f"Failed to reload commands cog: {e}")

    @commands.command(name="sync")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def sync_commands(self, ctx: commands.Context, spec: Optional[str] = None):
        """
        Refreshes/Syncs slash commands to Discord without duplicates.
        - !sync / !sync_poker: Syncs to this server (instant, no duplicates).
        - !sync global: Syncs globally to all servers.
        """
        from ...utils.logger import log

        # 1. Ensure in-memory tree is populated
        await self._ensure_commands_loaded()
        global_cmds = self.bot.tree.get_commands()
        log.info(f"Sync invoked by {ctx.author}. In-memory global commands: {[c.name for c in global_cmds]}")

        if spec == "global":
            # Clear guild-specific commands for this guild on Discord to prevent duplicate icons
            self.bot.tree.clear_commands(guild=ctx.guild)
            await self.bot.tree.sync(guild=ctx.guild)
            # Sync globally
            await self._ensure_commands_loaded()
            synced = await self.bot.tree.sync()
            log.info(f"Synced {len(synced)} global commands")
            await ctx.send(self.t("cmd_sync_global_done", count=len(synced)))
            return

        # Fast server-specific sync (Instant + ZERO duplicates):
        # 1. Clear any global commands on Discord API so they don't appear twice
        self.bot.tree.clear_commands(guild=None)
        await self.bot.tree.sync(guild=None)

        # 2. Restore in-memory commands and sync to this guild
        await self._ensure_commands_loaded()
        self.bot.tree.copy_global_to(guild=ctx.guild)
        synced_guild = await self.bot.tree.sync(guild=ctx.guild)
        log.info(f"Synced {len(synced_guild)} guild commands to {ctx.guild.name} ({ctx.guild.id})")

        await ctx.send(self.t("cmd_sync_done", count=len(synced_guild)))

    @commands.command(name="clear_commands")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def clear_commands(self, ctx: commands.Context):
        """Deletes all slash commands associated with the bot from Discord."""
        # 1. Clear Guild commands on Discord
        self.bot.tree.clear_commands(guild=ctx.guild)
        await self.bot.tree.sync(guild=ctx.guild)

        # 2. Clear Global commands on Discord
        self.bot.tree.clear_commands(guild=None)
        await self.bot.tree.sync(guild=None)

        # 3. Restore in-memory tree so future !sync immediately works
        await self._ensure_commands_loaded()

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
