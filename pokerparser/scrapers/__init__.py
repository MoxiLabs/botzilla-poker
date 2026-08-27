"""Scrapers package for Botzilla."""

from .base import BaseScraper
from .freeroll_password import FreeRollPasswordScraper
from .freerollpass import FreerollPassScraper
from .manager import ScraperManager, create_default_scrapers
from .network.http_client import HttpFetcher
from .parsers.base import BaseHtmlParser
from .parsers.freeroll_password import FreeRollPasswordParser
from .parsers.freerollpass import FreerollPassParser

__all__ = [
    "BaseScraper",
    "FreeRollPasswordScraper",
    "FreerollPassScraper",
    "ScraperManager",
    "create_default_scrapers",
    "HttpFetcher",
    "BaseHtmlParser",
    "FreeRollPasswordParser",
    "FreerollPassParser",
]
