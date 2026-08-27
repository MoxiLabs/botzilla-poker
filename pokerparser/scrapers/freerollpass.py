"""Scraper implementation for freerollpass.com."""

from typing import Optional
from .base import BaseScraper
from .parsers.freerollpass import FreerollPassParser
from .network.http_client import HttpFetcher


class FreerollPassScraper(BaseScraper):
    """Scraper targeting freerollpass.com."""

    def __init__(
        self,
        url: str = "https://freerollpass.com/",
        timezone: str = "Europe/Budapest",
        fetcher: Optional[HttpFetcher] = None,
    ):
        parser = FreerollPassParser(base_url=url, timezone=timezone)
        super().__init__(url=url, parser=parser, fetcher=fetcher)
