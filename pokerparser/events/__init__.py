"""Events package for Botzilla."""

from .bus import EventBus
from .events import (
    Event,
    NewTournamentsDiscoveredEvent,
    TournamentAlertTriggeredEvent,
)

__all__ = [
    "EventBus",
    "Event",
    "NewTournamentsDiscoveredEvent",
    "TournamentAlertTriggeredEvent",
]
