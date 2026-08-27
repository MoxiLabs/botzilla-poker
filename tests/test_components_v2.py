"""Unit tests for Discord Components V2 UI builders and LayoutViews."""

import os
import shutil
import tempfile
import unittest
from datetime import date, time
from unittest.mock import AsyncMock, MagicMock
import discord
from discord.ui import LayoutView, Container, Section, TextDisplay, ActionRow

from pokerparser.domain.models import Tournament
from pokerparser.bot.ui.components import TournamentComponentBuilder
from pokerparser.bot.ui.views import FreerollPaginatorView
from pokerparser.bot.ui.assets import AssetManager


class TestComponentsV2(unittest.IsolatedAsyncioTestCase):
    """Test suite verifying Discord Components V2 UI generation."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.asset_manager = AssetManager(base_dir=self.temp_dir)
        self.builder = TournamentComponentBuilder(
            asset_manager=self.asset_manager,
            high_value_threshold=500,
            timezone="Europe/Budapest",
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _sample_tournament(self, name="Stars Special", room="PokerStars", prize="$600", password="secret") -> Tournament:
        return Tournament.from_raw(
            name=name,
            room=room,
            date=date(2026, 8, 28),
            time=time(20, 0),
            is_all_day=False,
            prize=prize,
            password=password,
            source="freerollpass.com",
            url="https://freerollpass.com/sample",
        )

    async def test_build_tournament_container(self):
        """Test constructing Components V2 Container with accent color and details."""
        t = self._sample_tournament(prize="$600")
        container, attach = await self.builder.build_tournament_container(t, urgent=False)

        self.assertIsInstance(container, Container)
        # High value >= 500 should use Gold accent
        self.assertEqual(container.accent_color, self.builder.COLOR_GOLD)
        self.assertGreater(len(container.children), 1)

        # Ensure no duplicated emojis in details or footer
        texts = [item.content for item in container.children if isinstance(item, TextDisplay)]
        combined_text = "\n".join(texts)
        self.assertNotIn("💵 💵", combined_text)
        self.assertNotIn("🕒 🕒", combined_text)
        self.assertNotIn("🔑 🔑", combined_text)
        self.assertNotIn("🌐 🌐", combined_text)
        self.assertIn("💵 **", combined_text)

    async def test_build_tournament_layout(self):
        """Test constructing standalone LayoutView with Container and ActionRow buttons."""
        t = self._sample_tournament(password="pass123")
        layout, attach = await self.builder.build_tournament_layout(t, urgent=True, banner="🚨 Starting in 10 mins!")

        self.assertIsInstance(layout, LayoutView)
        self.assertGreaterEqual(len(layout.children), 2)  # Banner/Container and ActionRow

        # Check action row items (Link button + Copy Password button)
        action_rows = [c for c in layout.children if isinstance(c, ActionRow)]
        self.assertGreaterEqual(len(action_rows), 1)

    def test_build_help_layout(self):
        """Test constructing the instruction manual LayoutView with suffix."""
        builder_with_suffix = TournamentComponentBuilder(
            asset_manager=self.asset_manager,
            command_suffix="_poker",
        )
        help_view = builder_with_suffix.build_help_layout()
        self.assertIsInstance(help_view, LayoutView)
        self.assertEqual(len(help_view.children), 1)
        container = help_view.children[0]
        self.assertIsInstance(container, Container)
        self.assertEqual(container.accent_color, self.builder.COLOR_BLUE)

        # Ensure command_suffix is formatted into prefix commands and no double emojis
        help_texts = [item.content for item in container.children if isinstance(item, TextDisplay)]
        combined_text = "\n".join(help_texts)
        self.assertIn("!day_poker", combined_text)
        self.assertNotIn("🃏 🃏", combined_text)
        self.assertNotIn("📢 📢", combined_text)

    async def test_paginator_layout_view(self):
        """Test FreerollPaginatorView LayoutView pagination and components."""
        t1 = self._sample_tournament(name="T1", room="PokerStars")
        t2 = self._sample_tournament(name="T2", room="GGPoker")

        paginator = FreerollPaginatorView(
            tournaments=[t1, t2],
            component_builder=self.builder,
            author_id=123,
        )

        self.assertIsInstance(paginator, LayoutView)
        view, attach = await paginator.get_current_payload()

        # Should have Select menu row, Container, and Navigation row
        self.assertEqual(len(paginator.children), 3)

        # Test next page navigation
        mock_interaction = MagicMock()
        mock_interaction.response.edit_message = AsyncMock()
        await paginator._on_next(mock_interaction)
        self.assertEqual(paginator.current_page, 1)
        self.assertEqual(paginator.current_tournament, t2)
        mock_interaction.response.edit_message.assert_called_once()

    async def test_paginator_interaction_check(self):
        """Test interaction_check permissions for author and non-author users."""
        t1 = self._sample_tournament(name="T1", room="PokerStars")
        paginator = FreerollPaginatorView(
            tournaments=[t1],
            component_builder=self.builder,
            author_id=123,
        )

        # 1. Author should pass check
        author_interaction = MagicMock()
        author_interaction.user.id = 123
        author_interaction.data = {"custom_id": "nav_next"}
        self.assertTrue(await paginator.interaction_check(author_interaction))

        # 2. Non-author clicking Copy Password should pass check
        other_interaction_copy = MagicMock()
        other_interaction_copy.user.id = 999
        other_interaction_copy.data = {"custom_id": "copy_pwd"}
        self.assertTrue(await paginator.interaction_check(other_interaction_copy))

        # 3. Non-author clicking pagination should fail check and send ephemeral message
        other_interaction_nav = MagicMock()
        other_interaction_nav.user.id = 999
        other_interaction_nav.data = {"custom_id": "nav_next"}
        other_interaction_nav.response.send_message = AsyncMock()
        self.assertFalse(await paginator.interaction_check(other_interaction_nav))
    async def test_asset_manager_squarifies_rectangular_logo(self):
        """Test that rectangular logos are automatically padded to 1:1 square canvas to prevent Discord cropping."""
        import io
        from PIL import Image

        # Create a rectangular 200x60 test image
        rect_img = Image.new("RGBA", (200, 60), (255, 0, 0, 255))
        buf = io.BytesIO()
        rect_img.save(buf, format="PNG")

        room = "PokerStars"
        target_path = self.asset_manager.get_logo_path(room)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "wb") as f:
            f.write(buf.getvalue())

        # Ensure logo processes file
        res_path = await self.asset_manager.ensure_logo(room)
        self.assertEqual(res_path, target_path)

        # Inspect resulting image
        with Image.open(res_path) as final_img:
            w, h = final_img.size
            self.assertEqual(w, h, "Processed logo should have 1:1 aspect ratio")
            self.assertGreaterEqual(w, 200)


if __name__ == "__main__":
    unittest.main()

