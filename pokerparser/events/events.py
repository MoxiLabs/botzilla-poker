"""Domain and application event definitions."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from ..domain.models import Tournament


@dataclass
class Event:
    """Base class for all domain and application events."""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class NewTournamentsDiscoveredEvent(Event):
    """Fired when new, unnotified freerolls are detected by the watcher."""
    tournaments: List[Tournament] = field(default_factory=list)
    is_daily_summary: bool = False


@dataclass
class TournamentAlertTriggeredEvent(Event):
    """Fired when a tournament approaches its start time (warning or urgent threshold)."""
    tournament: Optional[Tournament] = None
    alert_type: str = "warning"  # "warning" or "urgent"
    minutes_left: int = 0
