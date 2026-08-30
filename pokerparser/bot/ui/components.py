"""Discord Components V2 layout and container builders for Botzilla."""

import os
from typing import Tuple, Optional
import discord
from discord.ui import LayoutView, Container, Section, TextDisplay, ActionRow, Button, Thumbnail, Separator

from ...domain.models import Tournament
from ...config.i18n import I18nService, default_i18n
from ...utils.datetime_utils import get_discord_timestamp
from .assets import AssetManager


class TournamentComponentBuilder:
    """Builder for constructing modern Discord Components V2 layouts, containers, and attachments."""

    COLOR_GOLD = 0xD4AF37        # Metallic Gold for High Value
    COLOR_NEPHRITE = 0x27AE60    # Deep Green for Normal
    COLOR_POMEGRANATE = 0xC0392B  # Royal Red for Urgent
    COLOR_BLUE = 0x2980B9        # Slate Blue for Help/Info
    COLOR_GRAY = 0x95A5A6        # Gray for Empty/Neutral

    def __init__(
        self,
        asset_manager: Optional[AssetManager] = None,
        i18n: Optional[I18nService] = None,
        high_value_threshold: int = 500,
        timezone: str = "Europe/Budapest",
        command_prefix: str = "!",
        command_suffix: str = "",
    ):
        self.asset_manager = asset_manager or AssetManager()
        self.i18n = i18n or default_i18n
        self.high_value_threshold = high_value_threshold
        self.timezone = timezone
        self.command_prefix = command_prefix
        self.command_suffix = command_suffix

    def get_accent_color(self, tournament: Tournament, urgent: bool = False) -> int:
        """Determine accent color based on urgency and prize threshold."""
        if urgent:
            return self.COLOR_POMEGRANATE
        if tournament.prize_value >= self.high_value_threshold:
            return self.COLOR_GOLD
        return self.COLOR_NEPHRITE

    async def build_tournament_container(
        self,
        tournament: Tournament,
        urgent: bool = False,
        page_info: Optional[str] = None,
    ) -> Tuple[Container, Optional[discord.File]]:
        """Constructs a styled Container with tournament details and optional logo file attachment."""
        accent_color = self.get_accent_color(tournament, urgent=urgent)
        container = Container(accent_color=accent_color)

        # 1. Header Section with Room Logo Thumbnail
        logo_path = await self.asset_manager.ensure_logo(tournament.room)
        file_attachment = None

        header_text = f"### {tournament.name}\n**{tournament.room}**"

        if logo_path and os.path.exists(logo_path):
            filename = os.path.basename(logo_path)
            file_attachment = discord.File(logo_path, filename=filename)
            thumb = Thumbnail(f"attachment://{filename}")
            container.add_item(Section(header_text, accessory=thumb))
        else:
            container.add_item(TextDisplay(header_text))

        container.add_item(Separator(visible=True))

        # 2. Key Details (Prize, Start Time, Password)
        if tournament.is_all_day or tournament.time is None:
            time_display = self.i18n("fmt_all_day", date=tournament.date.strftime("%d.%m.%Y"))
        else:
            timestamp = get_discord_timestamp(tournament.start_datetime, self.timezone)
            time_display = f"**{tournament.start_datetime.strftime('%H:%M %d.%m.%Y')}** (<t:{timestamp}:R>)"

        password_text = f"`{tournament.password}`" if tournament.has_password else "—"

        details_md = (
            f"**{self.i18n('label_prize')}:** {tournament.prize}\n"
            f"**{self.i18n('label_start')}:** {time_display}\n"
            f"**{self.i18n('label_password')}:** {password_text}"
        )
        container.add_item(TextDisplay(details_md))

        # 3. Footer info (Source & Page info)
        footer_parts = [f"{self.i18n('label_source')}: {tournament.source}"]
        if page_info:
            footer_parts.append(page_info)
        footer_parts.append(self.i18n("help_footer"))

        container.add_item(TextDisplay(f"-# {' • '.join(footer_parts)}"))

        return container, file_attachment

    async def build_tournament_layout(
        self,
        tournament: Tournament,
        urgent: bool = False,
        banner: Optional[str] = None,
    ) -> Tuple[LayoutView, Optional[discord.File]]:
        """Constructs a standalone LayoutView containing banner, Container, and ActionRow."""
        view = LayoutView(timeout=None)

        if banner:
            view.add_item(TextDisplay(banner))

        container, file_attachment = await self.build_tournament_container(tournament, urgent=urgent)
        view.add_item(container)

        action_row = ActionRow()
        if tournament.url:
            action_row.add_item(
                Button(
                    label=self.i18n("btn_link"),
                    style=discord.ButtonStyle.link,
                    url=tournament.url,
                )
            )

        if tournament.has_password:
            copy_btn = Button(
                label=self.i18n("btn_copy_pw"),
                style=discord.ButtonStyle.success,
                custom_id="copy_pwd",
            )

            async def _on_copy(interaction: discord.Interaction):
                await interaction.response.send_message(
                    content=self.i18n("password_copied", password=tournament.password),
                    ephemeral=True,
                )

            copy_btn.callback = _on_copy
            action_row.add_item(copy_btn)

        if action_row.children:
            view.add_item(action_row)

        return view, file_attachment

    def build_help_layout(self) -> LayoutView:
        """Constructs the instruction guide using a styled Components V2 Container."""
        view = LayoutView(timeout=180.0)
        container = Container(accent_color=self.COLOR_BLUE)

        # Header
        container.add_item(TextDisplay(f"### {self.i18n('help_title')}\n{self.i18n('help_description')}"))
        container.add_item(Separator(visible=True))

        # Slash Commands
        slash_list = [
            f"`/day` `[room]` `[min_prize]` — {self.i18n('help_slash_day')}",
            f"`/next` — {self.i18n('help_slash_next')}",
            f"`/help` — {self.i18n('help_slash_help')}",
        ]
        container.add_item(
            TextDisplay(f"**{self.i18n('help_header_slash')}**\n" + "\n".join(slash_list))
        )
        container.add_item(Separator(visible=True))

        # Prefix Commands
        prefix_list = [
            self.i18n("help_cmd_day", suffix=self.command_suffix),
            self.i18n("help_cmd_next", suffix=self.command_suffix),
            self.i18n("help_cmd_help", suffix=self.command_suffix),
        ]
        container.add_item(
            TextDisplay(f"**{self.i18n('help_header_prefix')}**\n" + "\n".join(prefix_list))
        )
        container.add_item(Separator(visible=True))

        # Notifications & Footer
        container.add_item(
            TextDisplay(
                f"**{self.i18n('help_notif_title')}**\n{self.i18n('help_notif_desc')}\n\n-# Botzilla Poker"
            )
        )

        view.add_item(container)
        return view

    def build_info_layout(
        self, title: str, description: str, color: Optional[int] = None
    ) -> LayoutView:
        """Constructs a simple informational LayoutView with a colored Container."""
        view = LayoutView(timeout=60.0)
        container = Container(accent_color=color or self.COLOR_BLUE)
        container.add_item(TextDisplay(f"### {title}\n{description}"))
        view.add_item(container)
        return view
