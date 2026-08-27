"""Localization and translation service for Botzilla."""

import json
import os
import sys
from typing import Any, Callable, Dict, Optional


class I18nService:
    """Service to load, cache, and format localized strings with fallback support."""

    def __init__(
        self,
        locale: str = "hu",
        fallback_locale: str = "en",
        locales_dir: Optional[str] = None,
    ):
        self.locale = locale
        self.fallback_locale = fallback_locale
        if locales_dir:
            self.locales_dir = locales_dir
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.locales_dir = os.path.join(base_dir, "locales")
        
        self._cache: Dict[str, Dict[str, Any]] = {}
        # Pre-load configured and fallback locales
        self._ensure_loaded(self.locale)
        if self.fallback_locale != self.locale:
            self._ensure_loaded(self.fallback_locale)

    def _ensure_loaded(self, locale: str) -> Dict[str, Any]:
        """Loads and caches translations for the given locale."""
        if locale in self._cache:
            return self._cache[locale]

        translations = self._load_translations(locale)
        self._cache[locale] = translations
        return translations

    def _load_translations(self, locale: str) -> Dict[str, Any]:
        """Loads translations from JSON file."""
        possible_paths = [
            os.path.join(self.locales_dir, f"{locale}.json"),
            os.path.join(os.getcwd(), "locales", f"{locale}.json"),
        ]
        for path in possible_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    print(f"Error loading locale file {path}: {e}", file=sys.stderr)
        return {}

    def set_locale(self, locale: str):
        """Switch current active locale."""
        self.locale = locale
        self._ensure_loaded(locale)

    def translate(self, key: str, locale: Optional[str] = None, **kwargs) -> Any:
        """
        Translate a key with optional formatting variables.
        Falls back to fallback_locale and then key itself if missing.
        """
        target_locale = locale or self.locale
        translations = self._ensure_loaded(target_locale)
        
        text = translations.get(key)
        if text is None and target_locale != self.fallback_locale:
            fallback_trans = self._ensure_loaded(self.fallback_locale)
            text = fallback_trans.get(key)

        if text is None:
            text = key

        if isinstance(text, str) and kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    def get_translator(self, locale: Optional[str] = None) -> Callable[..., Any]:
        """Returns a bound callable for translating with a specific or default locale."""
        target_locale = locale or self.locale
        return lambda key, **kwargs: self.translate(key, locale=target_locale, **kwargs)

    def __call__(self, key: str, **kwargs) -> Any:
        return self.translate(key, **kwargs)


# Global default instance retained for legacy/fallback access
default_i18n = I18nService()


def t(key: str, **kwargs) -> Any:
    """Global fallback translation helper function."""
    return default_i18n.translate(key, **kwargs)

