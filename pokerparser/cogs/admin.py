import discord
from discord.ext import commands
from typing import Optional
from ..core import t, config

class AdminCommands(commands.Cog):
    """Administrative commands for bot maintenance and command syncing"""
    
    def __init__(self, bot):
        self.bot = bot
        self.command_suffix = config.get("command_suffix", "")

    @commands.command(name=f"sync{config.get('command_suffix', '')}")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def sync_prefix(self, ctx: commands.Context, spec: Optional[str] = None):
        """
        Refreshes/Syncs slash commands to Discord.
        - !sync_poker: Syncs to the current server (fast).
        - !sync_poker global: Syncs globally (slow, up to 1 hour).
        - !sync_poker copy: Copies global commands and syncs to this server.
        """
        if spec == "global":
            synced = await self.bot.tree.sync()
            await ctx.send(t("cmd_sync_global_done", count=len(synced)))
        elif spec == "copy":
            self.bot.tree.copy_global_to(guild=ctx.guild)
            synced = await self.bot.tree.sync(guild=ctx.guild)
            await ctx.send(t("cmd_sync_copy_done", count=len(synced)))
        else:
            synced = await self.bot.tree.sync(guild=ctx.guild)
            await ctx.send(t("cmd_sync_done", count=len(synced)))

    @commands.command(name=f"clear_commands{config.get('command_suffix', '')}")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def clear_commands_prefix(self, ctx: commands.Context):
        """Deletes all slash commands associated with the bot from Discord."""
        # Global clear
        self.bot.tree.clear_commands(guild=None)
        await self.bot.tree.sync(guild=None)
        
        # Guild clear
        self.bot.tree.clear_commands(guild=ctx.guild)
        await self.bot.tree.sync(guild=ctx.guild)
        
        prefix = config.get("command_prefix", "!")
        sync_cmd = f"{prefix}sync{self.command_suffix}"
        await ctx.send(t("cmd_clear_done", cmd=sync_cmd))

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
