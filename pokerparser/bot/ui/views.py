"""Interactive Discord UI views and components for Discord Components V2."""

from typing import List, Optional, Sequence
import discord
from discord.ui import LayoutView, Container, ActionRow, Button, Select, TextDisplay

from ...domain.models import Tournament
from ...config.i18n import I18nService, default_i18n


class FreerollPaginatorView(LayoutView):
    """Interactive Components V2 LayoutView with Poker Room filter dropdown and carousel navigation."""

    def __init__(
        self,
        tournaments: Sequence[Tournament],
        component_builder,
        author_id: Optional[int] = None,
        i18n: Optional[I18nService] = None,
        timeout: float = 300.0,
    ):
        super().__init__(timeout=timeout)
        self.all_tournaments = list(tournaments)
        self.filtered_tournaments = list(tournaments)
        self.component_builder = component_builder
        self.i18n = i18n or getattr(component_builder, "i18n", default_i18n)
        self.author_id = author_id
        self.current_page = 0
        self.selected_room = "all"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Allow password copying by anyone, but restrict pagination to the command author if author_id is set."""
        if self.author_id is None or interaction.user.id == self.author_id:
            return True

        custom_id = interaction.data.get("custom_id", "")
        if custom_id == "copy_pwd":
            return True

        await interaction.response.send_message(
            content=self.i18n("no_permission") if self.i18n("no_permission") != "no_permission" else "Only the command author can navigate pages.",
            ephemeral=True,
        )
        return False

    @property
    def current_tournament(self) -> Optional[Tournament]:
        """Get the currently selected tournament."""
        if not self.filtered_tournaments or self.current_page >= len(self.filtered_tournaments):
            return None
        return self.filtered_tournaments[self.current_page]

    async def get_current_payload(self):
        """Reconstructs the Components V2 tree (Select menu, Container, and Buttons)."""
        self.clear_items()

        # 1. Top ActionRow: Poker Room Dropdown
        room_row = ActionRow()
        distinct_rooms = sorted({tourney.room.name for tourney in self.all_tournaments})
        options = [
            discord.SelectOption(
                label=f"All Rooms ({len(self.all_tournaments)})",
                value="all",
                default=(self.selected_room == "all"),
            )
        ]

        for room in distinct_rooms[:24]:
            count = sum(1 for tourney in self.all_tournaments if tourney.room.name == room)
            options.append(
                discord.SelectOption(
                    label=f"{room} ({count})",
                    value=room,
                    default=(self.selected_room == room),
                )
            )

        select_menu = Select(
            placeholder="Filter by Poker Room...",
            options=options,
        )
        select_menu.callback = self._on_select_room
        room_row.add_item(select_menu)
        self.add_item(room_row)

        # 2. Middle Container: Tournament Card
        tournament = self.current_tournament
        file_attachment = None

        if not tournament:
            empty_container = Container(accent_color=0x95A5A6)
            empty_container.add_item(
                TextDisplay(f"### {self.i18n('no_upcoming_freeroll')}\nNo freerolls match the selected filter.")
            )
            self.add_item(empty_container)
            return self, None

        total_pages = len(self.filtered_tournaments)
        page_info = f"Page {self.current_page + 1}/{total_pages}"
        container, file_attachment = await self.component_builder.build_tournament_container(
            tournament, page_info=page_info
        )
        self.add_item(container)

        # 3. Bottom ActionRow: Navigation & Action Buttons
        nav_row = ActionRow()

        prev_btn = Button(
            label="◀",
            style=discord.ButtonStyle.primary,
            disabled=(self.current_page <= 0),
        )
        prev_btn.callback = self._on_prev
        nav_row.add_item(prev_btn)

        page_btn = Button(
            label=f"{self.current_page + 1} / {total_pages}",
            style=discord.ButtonStyle.secondary,
            disabled=True,
        )
        nav_row.add_item(page_btn)

        next_btn = Button(
            label="▶",
            style=discord.ButtonStyle.primary,
            disabled=(self.current_page >= total_pages - 1),
        )
        next_btn.callback = self._on_next
        nav_row.add_item(next_btn)

        if tournament.url:
            nav_row.add_item(
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
            copy_btn.callback = self._on_copy_password
            nav_row.add_item(copy_btn)

        self.add_item(nav_row)
        return self, file_attachment

    async def _update_page(self, interaction: discord.Interaction):
        """Reconstructs the Components V2 payload and updates the Discord message."""
        _, attach = await self.get_current_payload()
        attachments = [attach] if attach else []
        await interaction.response.edit_message(view=self, attachments=attachments)

    async def _on_prev(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
        await self._update_page(interaction)

    async def _on_next(self, interaction: discord.Interaction):
        if self.current_page < len(self.filtered_tournaments) - 1:
            self.current_page += 1
        await self._update_page(interaction)

    async def _on_select_room(self, interaction: discord.Interaction):
        select = interaction.data.get("values", ["all"])[0]
        self.selected_room = select
        self.current_page = 0

        if select == "all":
            self.filtered_tournaments = list(self.all_tournaments)
        else:
            self.filtered_tournaments = [tourney for tourney in self.all_tournaments if tourney.room.name == select]

        await self._update_page(interaction)

    async def _on_copy_password(self, interaction: discord.Interaction):
        active = self.current_tournament
        password = active.password if active else "n/a"
        await interaction.response.send_message(
            content=self.i18n("password_copied", password=password),
            ephemeral=True,
        )
