"""Scraper implementation for freeroll-password.com."""

from typing import Optional
from .base import BaseScraper
from .parsers.freeroll_password import FreeRollPasswordParser
from .network.http_client import HttpFetcher


class FreeRollPasswordScraper(BaseScraper):
    """Scraper targeting freeroll-password.com."""

    def __init__(
        self,
        url: str = "https://www.freeroll-password.com/",
        timezone: str = "Europe/Budapest",
        fetcher: Optional[HttpFetcher] = None,
    ):
        parser = FreeRollPasswordParser(base_url=url, timezone=timezone)
        super().__init__(url=url, parser=parser, fetcher=fetcher)
