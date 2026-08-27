"""Unit tests for I18nService and localization injection."""

import unittest
from datetime import date, time
from pokerparser.config.i18n import I18nService
from pokerparser.domain.models import Tournament
from pokerparser.bot.ui.components import TournamentComponentBuilder


class TestI18n(unittest.TestCase):
    """Test suite verifying multi-locale support, fallback behavior, and component localization."""

    def setUp(self):
        self.i18n_hu = I18nService(locale="hu", fallback_locale="en")
        self.i18n_en = I18nService(locale="en", fallback_locale="hu")

    def test_translation_locales(self):
        """Test translating keys in Hungarian and English."""
        self.assertEqual(self.i18n_hu.translate("test_ok"), "🧪 Teszt OK! A bot fut.")
        self.assertEqual(self.i18n_en.translate("test_ok"), "🧪 Test OK! The bot is running.")

    def test_translation_formatting_kwargs(self):
        """Test formatting placeholders in translations."""
        hu_formatted = self.i18n_hu.translate("error_cooldown", retry_after="4.2")
        self.assertIn("4.2", hu_formatted)
        self.assertIn("másodpercet", hu_formatted)

        en_formatted = self.i18n_en.translate("error_cooldown", retry_after="4.2")
        self.assertIn("4.2s", en_formatted)
        self.assertIn("Please wait", en_formatted)

    def test_locale_switching(self):
        """Test dynamically switching active locale on I18nService."""
        service = I18nService(locale="hu")
        self.assertEqual(service.translate("test_ok"), "🧪 Teszt OK! A bot fut.")

        service.set_locale("en")
        self.assertEqual(service.translate("test_ok"), "🧪 Test OK! The bot is running.")

    def test_fallback_to_secondary_locale(self):
        """Test falling back to secondary locale when key is missing in custom dict."""
        import tempfile
        import json
        import os
        import shutil

        temp_dir = tempfile.mkdtemp()
        try:
            # Create a partial locale file with only one key
            de_file = os.path.join(temp_dir, "de.json")
            with open(de_file, "w", encoding="utf-8") as f:
                json.dump({"custom_key": "Hallo"}, f)

            # Create fallback en.json
            en_file = os.path.join(temp_dir, "en.json")
            with open(en_file, "w", encoding="utf-8") as f:
                json.dump({"fallback_key": "Hello from fallback", "common": "English"}, f)

            service = I18nService(locale="de", fallback_locale="en", locales_dir=temp_dir)
            # 1. Key in primary
            self.assertEqual(service.translate("custom_key"), "Hallo")
            # 2. Key missing in primary but in fallback
            self.assertEqual(service.translate("fallback_key"), "Hello from fallback")
            # 3. Key completely missing
            self.assertEqual(service.translate("unknown_key"), "unknown_key")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_format_error_resilience(self):
        """Test that translation with missing format placeholder does not crash."""
        # 'starts_in_minutes' expects {min}, passing no args should return template string safely
        result = self.i18n_hu.translate("starts_in_minutes")
        self.assertIn("{min}", result)

    def test_array_translation_support(self):
        """Test retrieving array translations such as status_messages."""
        messages_hu = self.i18n_hu.translate("status_messages")
        self.assertIsInstance(messages_hu, list)
        self.assertGreater(len(messages_hu), 0)

    def test_component_builder_uses_injected_i18n(self):
        """Test that TournamentComponentBuilder uses its injected locale."""
        builder_hu = TournamentComponentBuilder(i18n=self.i18n_hu)
        builder_en = TournamentComponentBuilder(i18n=self.i18n_en)

        help_hu = builder_hu.build_help_layout()
        help_en = builder_en.build_help_layout()

        # Check container text content for Hungarian vs English
        text_hu = [item.content for item in help_hu.children[0].children if hasattr(item, "content")]
        text_en = [item.content for item in help_en.children[0].children if hasattr(item, "content")]

        combined_hu = "\n".join(text_hu)
        combined_en = "\n".join(text_en)

        self.assertIn("Poker Bot Segítség", combined_hu)
        self.assertIn("Poker Bot Help", combined_en)


if __name__ == "__main__":
    unittest.main()
