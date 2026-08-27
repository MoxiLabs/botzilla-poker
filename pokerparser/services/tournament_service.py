"""Tournament service managing freeroll data aggregation and filtering."""

from datetime import datetime, timedelta
from typing import List, Optional
import aiohttp

from ..domain.models import Tournament
from ..scrapers.manager import ScraperManager
from ..utils.logger import log


class TournamentService:
    """Service to query, cache, and filter poker freeroll tournaments with TTL support."""

    def __init__(self, scraper_manager: ScraperManager, cache_ttl_seconds: int = 300):
        self.scraper_manager = scraper_manager
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cached_tournaments: List[Tournament] = []
        self._last_fetched: Optional[datetime] = None

    def set_session(self, session: Optional[aiohttp.ClientSession]):
        """Propagate shared aiohttp ClientSession to the underlying scraper manager."""
        self.scraper_manager.set_session(session)

    @property
    def cached_tournaments(self) -> List[Tournament]:
        """Returns the in-memory cached tournament list."""
        return self._cached_tournaments

    @property
    def is_cache_expired(self) -> bool:
        """Checks whether the cache is empty or has exceeded its TTL."""
        if self._last_fetched is None or not self._cached_tournaments:
            return True
        elapsed = (datetime.now() - self._last_fetched).total_seconds()
        return elapsed >= self.cache_ttl_seconds

    async def fetch_tournaments(self) -> List[Tournament]:
        """Fetch latest tournaments from all scrapers and update cache."""
        log.info("Fetching freerolls from all scraper sources...")
        tournaments = await self.scraper_manager.fetch_all()
        self._cached_tournaments = tournaments
        self._last_fetched = datetime.now()
        log.info(f"Successfully fetched and cached {len(tournaments)} tournaments.")
        return tournaments

    async def get_all_tournaments(self, force_refresh: bool = False) -> List[Tournament]:
        """Get all tournaments, fetching if cache is expired or if refresh is requested."""
        if force_refresh or self.is_cache_expired:
            return await self.fetch_tournaments()
        return self._cached_tournaments

    def filter_tournaments(
        self,
        tournaments: List[Tournament],
        room: Optional[str] = None,
        min_prize: Optional[int] = None,
    ) -> List[Tournament]:
        """Filters a list of tournaments by poker room and minimum prize threshold."""
        filtered = list(tournaments)
        if room:
            room_clean = room.lower().replace(" ", "").replace("-", "").replace(".", "")
            filtered = [e for e in filtered if room_clean in e.room.clean_id]
        if min_prize is not None:
            filtered = [e for e in filtered if e.prize_value >= min_prize]
        return filtered

    async def get_upcoming_tournaments(
        self,
        hours: int = 24,
        room: Optional[str] = None,
        min_prize: Optional[int] = None,
        force_refresh: bool = False,
    ) -> List[Tournament]:
        """Get tournaments occurring in the next N hours with optional room and min_prize filtering."""
        tournaments = await self.get_all_tournaments(force_refresh=force_refresh)
        now = datetime.now()
        cutoff = now + timedelta(hours=hours)

        upcoming = [e for e in tournaments if now <= e.start_datetime <= cutoff]
        return self.filter_tournaments(upcoming, room=room, min_prize=min_prize)

    async def get_next_tournament(
        self,
        room: Optional[str] = None,
        min_prize: Optional[int] = None,
        force_refresh: bool = False,
    ) -> Optional[Tournament]:
        """Get the single nearest upcoming timed tournament."""
        tournaments = await self.get_all_tournaments(force_refresh=force_refresh)
        now = datetime.now()

        future_timed = [e for e in tournaments if not e.is_all_day and e.start_datetime > now]
        filtered = self.filter_tournaments(future_timed, room=room, min_prize=min_prize)
        return filtered[0] if filtered else None
