"""User-facing hybrid commands Cog for poker tournaments using Discord Components V2."""

from typing import TYPE_CHECKING, Optional
from datetime import datetime
import discord
from discord.ext import commands

from ..ui.views import FreerollPaginatorView

if TYPE_CHECKING:
    from ..client import PokerBot


class PokerCommands(commands.Cog):
    """Cog providing user commands to query poker freerolls using Components V2."""

    def __init__(self, bot: "PokerBot"):
        self.bot = bot

    def t(self, key: str, **kwargs):
        """Helper to translate using bot's injected i18n service."""
        return self.bot.i18n.translate(key, **kwargs)

    @commands.hybrid_command(
        name="day",
        description="Shows freerolls for the next 24 hours with interactive pagination and filters",
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def cmd_day(
        self,
        ctx: commands.Context,
        room: Optional[str] = None,
        min_prize: Optional[int] = None,
    ):
        """
        Shows freerolls scheduled in the next 24 hours.
        Optional filters:
        - room: Filter by poker room name (e.g. PokerStars, GGPoker)
        - min_prize: Filter by minimum numeric prize pool (e.g. 100)
        """
        upcoming = await self.bot.tournament_service.get_upcoming_tournaments(
            hours=24, room=room, min_prize=min_prize
        )

        if not upcoming:
            empty_view = self.bot.component_builder.build_info_layout(
                self.t("no_freerolls_24h"),
                "No tournaments match your criteria in the next 24 hours.",
                color=self.bot.component_builder.COLOR_GRAY,
            )
            await ctx.send(view=empty_view, ephemeral=True)
            return

        paginator = FreerollPaginatorView(
            tournaments=upcoming,
            component_builder=self.bot.component_builder,
            author_id=ctx.author.id,
            i18n=self.bot.i18n,
        )

        _, attach = await paginator.get_current_payload()
        if attach:
            await ctx.send(view=paginator, file=attach)
        else:
            await ctx.send(view=paginator)

    @commands.hybrid_command(name="next", description="Shows the very next upcoming freeroll")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def cmd_next(self, ctx: commands.Context):
        """Shows the single nearest upcoming freeroll."""
        nxt = await self.bot.tournament_service.get_next_tournament()
        if not nxt:
            empty_view = self.bot.component_builder.build_info_layout(
                self.t("no_upcoming_freeroll"),
                "No upcoming freerolls found.",
                color=self.bot.component_builder.COLOR_GRAY,
            )
            await ctx.send(view=empty_view)
            return

        delta = nxt.start_datetime - datetime.now()
        total_minutes = int(delta.total_seconds() / 60)
        banner = self.t("next_freeroll") + self.t("starts_in_minutes", min=total_minutes)

        layout_view, attach = await self.bot.component_builder.build_tournament_layout(
            nxt, banner=banner
        )
        if attach:
            await ctx.send(view=layout_view, file=attach)
        else:
            await ctx.send(view=layout_view)

    @commands.hybrid_command(name="debug", description="Shows technical info about loaded freerolls")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def cmd_debug(self, ctx: commands.Context):
        """Shows technical info about loaded freerolls."""
        events = await self.bot.tournament_service.get_all_tournaments(force_refresh=True)
        debug_view = self.bot.component_builder.build_info_layout(
            "🔧 Debug Info",
            self.t("debug_freerolls_loaded", count=len(events)),
            color=self.bot.component_builder.COLOR_BLUE,
        )
        await ctx.send(view=debug_view, ephemeral=True)

    @commands.hybrid_command(name="test", description="Pings the bot to check if it is alive")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def cmd_test(self, ctx: commands.Context):
        """Pings the bot to check if it is online."""
        test_view = self.bot.component_builder.build_info_layout(
            "🧪 Healthcheck",
            self.t("test_ok"),
            color=self.bot.component_builder.COLOR_NEPHRITE,
        )
        await ctx.send(view=test_view)

    @commands.hybrid_command(name="help", description="Shows the poker bot's instruction manual")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def cmd_help(self, ctx: commands.Context):
        """Displays help and command instructions."""
        help_view = self.bot.component_builder.build_help_layout()
        await ctx.send(view=help_view)


async def setup(bot: "PokerBot"):
    await bot.add_cog(PokerCommands(bot))
