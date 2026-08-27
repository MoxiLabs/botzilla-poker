"""Alert service managing notification triggers and deduplication."""

from datetime import datetime, timedelta, date
from typing import Dict, List, Set, Tuple, Optional

from ..domain.models import Tournament
from ..storage.repository import EventRepository
from ..config.settings import AlertThresholds


class AlertService:
    """Handles notification thresholds, deduplication, and database tracking."""

    def __init__(self, repository: EventRepository, thresholds: AlertThresholds):
        self.repository = repository
        self.thresholds = thresholds
        # In-memory alert cache: (event_hash, alert_type) -> sent_at datetime
        self._sent_alerts: Dict[Tuple[str, str], datetime] = {}

    async def get_unnotified_events(self, events: List[Tournament]) -> List[Tournament]:
        """Filter list to only events that have not yet been logged in the DB (batch)."""
        return await self.repository.get_unnotified_events(events)

    async def mark_event_sent(self, event: Tournament):
        """Persist event as sent in the database."""
        await self.repository.add_sent_event(event)

    async def mark_events_sent(self, events: List[Tournament]):
        """Persist a batch of events as sent in the database in a single transaction."""
        await self.repository.add_sent_events(events)

    async def has_sent_today(self, target_date: date) -> bool:
        """Check if any daily summary has been sent today."""
        return await self.repository.has_sent_today(target_date)

    def get_due_timed_alerts(
        self, events: List[Tournament], now: Optional[datetime] = None
    ) -> List[Tuple[Tournament, str, int]]:
        """
        Calculate which tournaments need immediate alerts (warning or urgent).
        Returns list of (Tournament, alert_type, minutes_left)
        """
        current_time = now or datetime.now()
        due: List[Tuple[Tournament, str, int]] = []

        warning_threshold = self.thresholds.warning
        urgent_threshold = self.thresholds.urgent

        for event in events:
            if event.is_all_day or event.time is None:
                continue

            delta = event.start_datetime - current_time
            total_minutes = int(delta.total_seconds() / 60)

            # 1. Urgent alert (e.g. < 10 mins)
            if 0 <= total_minutes < urgent_threshold:
                key = (event.event_hash, "urgent")
                if key not in self._sent_alerts:
                    due.append((event, "urgent", total_minutes))

            # 2. Warning alert (e.g. 10 <= min < 60)
            elif urgent_threshold <= total_minutes < warning_threshold:
                key = (event.event_hash, "warning")
                if key not in self._sent_alerts:
                    due.append((event, "warning", total_minutes))

        return due

    def mark_timed_alert_sent(
        self, event: Tournament, alert_type: str, sent_at: Optional[datetime] = None
    ):
        """Mark a timed alert as sent in memory using unique event hash."""
        self._sent_alerts[(event.event_hash, alert_type)] = sent_at or datetime.now()

    async def cleanup(self, today: date, current_time: Optional[datetime] = None):
        """Cleanup old database records and prune in-memory alert cache."""
        now = current_time or datetime.now()

        # Database cleanup
        await self.repository.cleanup_old_events(today)

        # In-memory prune (older than 2 hours)
        cutoff = now - timedelta(hours=2)
        self._sent_alerts = {
            k: sent_time for k, sent_time in self._sent_alerts.items()
            if sent_time > cutoff
        }
