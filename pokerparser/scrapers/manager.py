"""Manager to coordinate and run multiple tournament scrapers."""

import asyncio
from typing import List, Sequence, Optional, Dict, Set
import aiohttp

from .base import BaseScraper
from ..domain.models import Tournament
from ..utils.logger import log


def merge_tournaments(tournaments: List[Tournament]) -> List[Tournament]:
    """Merges duplicate tournaments across scrapers, combining best password, prize, and source info."""
    merged: Dict[str, Tournament] = {}
    sources_map: Dict[str, Set[str]] = {}

    for tourney in tournaments:
        h = tourney.event_hash
        if h not in merged:
            merged[h] = tourney
            sources_map[h] = {s.strip() for s in tourney.source.split(",") if s.strip()}
        else:
            existing = merged[h]
            # Merge password: pick valid password if available
            password = existing.password
            if not existing.has_password and tourney.has_password:
                password = tourney.password

            # Merge prize: pick higher numeric value or non-empty
            prize = existing.prize
            if tourney.prize_value > existing.prize_value or (existing.prize_value == 0 and tourney.prize_value > 0):
                prize = tourney.prize

            # Merge sources with O(1) set operations
            if tourney.source:
                new_sources = {s.strip() for s in tourney.source.split(",") if s.strip()}
                sources_map[h].update(new_sources)

            url = existing.url or tourney.url

            merged[h] = Tournament(
                name=existing.name if len(existing.name) >= len(tourney.name) else tourney.name,
                room=existing.room,
                date=existing.date,
                time=existing.time,
                is_all_day=existing.is_all_day and tourney.is_all_day,
                prize=prize,
                password=password,
                source=", ".join(sorted(sources_map[h])),
                url=url,
            )

    result = list(merged.values())
    result.sort(key=lambda x: x.start_datetime)
    return result


class ScraperManager:
    """Orchestrates scraping from multiple sources concurrently."""

    def __init__(self, scrapers: Sequence[BaseScraper]):
        self.scrapers = list(scrapers)

    def set_session(self, session: Optional[aiohttp.ClientSession]):
        """Propagate shared aiohttp ClientSession to all registered scrapers."""
        for scraper in self.scrapers:
            scraper.set_session(session)

    def add_scraper(self, scraper: BaseScraper):
        """Add an additional scraper to the manager."""
        self.scrapers.append(scraper)

    async def fetch_all(self) -> List[Tournament]:
        """Fetch tournaments concurrently from all registered scrapers and merge duplicates."""
        if not self.scrapers:
            return []

        tasks = [scraper.get_tournaments() for scraper in self.scrapers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        events: List[Tournament] = []
        for scraper, result in zip(self.scrapers, results):
            if isinstance(result, list):
                events.extend(result)
            elif isinstance(result, Exception):
                log.error(f"Scraper failed for {scraper.source_name}: {result}")

        return merge_tournaments(events)


def create_default_scrapers(url_password: str, url_pass: str, timezone: str = "Europe/Budapest") -> List[BaseScraper]:
    """Factory helper to construct all configured scraper instances dynamically."""
    from .freeroll_password import FreeRollPasswordScraper
    from .freerollpass import FreerollPassScraper

    return [
        FreeRollPasswordScraper(url=url_password, timezone=timezone),
        FreerollPassScraper(url=url_pass, timezone=timezone),
    ]
