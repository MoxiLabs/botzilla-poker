"""Base Scraper coordinating HttpFetcher and BaseHtmlParser."""

import asyncio
from typing import List, Optional
import aiohttp

from .network.http_client import HttpFetcher
from .network.circuit_breaker import CircuitBreaker
from .parsers.base import BaseHtmlParser
from ..domain.models import Tournament
from ..utils.logger import log


class BaseScraper:
    """Combines an HttpFetcher, BaseHtmlParser, and CircuitBreaker to scrape tournaments resiliently."""

    def __init__(
        self,
        url: str,
        parser: Optional[BaseHtmlParser] = None,
        fetcher: Optional[HttpFetcher] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        self.url = url
        self.parser = parser
        self.fetcher = fetcher or HttpFetcher()
        self.circuit_breaker = circuit_breaker or CircuitBreaker(
            name=self.source_name,
            failure_threshold=3,
            cooldown_seconds=600.0,
        )

    def set_session(self, session: Optional[aiohttp.ClientSession]):
        """Inject shared aiohttp ClientSession into the fetcher."""
        self.fetcher.session = session

    @property
    def source_name(self) -> str:
        """Domain or identifier of the source."""
        if self.parser:
            return self.parser.source_name
        return "base"

    async def get_tournaments(self) -> List[Tournament]:
        """Fetch HTML through fetcher and parse it in thread pool with circuit breaker protection."""
        if not self.parser:
            return []

        if not self.circuit_breaker.can_execute():
            log.warning(
                f"[{self.source_name}] Circuit breaker is OPEN. Skipping scrape to avoid overloading external service."
            )
            return []

        try:
            html = await self.fetcher.fetch_text(self.url)
            tournaments = await asyncio.to_thread(self.parser.parse, html)
            self.circuit_breaker.record_success()
            return tournaments
        except Exception as e:
            self.circuit_breaker.record_failure(e)
            log.error(f"Scraper error for {self.source_name} ({self.url}): {e}")
            return []
