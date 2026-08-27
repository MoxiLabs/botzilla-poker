"""Botzilla Poker Bot - Modular Poker Freeroll Parser and Discord Bot."""

from .config import Settings, get_settings, I18nService, t
from .domain import Tournament, Prize, PokerRoom
from .scrapers import BaseScraper, FreeRollPasswordScraper, FreerollPassScraper, ScraperManager, HttpFetcher
from .storage import Database, EventRepository
from .services import TournamentService, AlertService
from .events import EventBus, Event, NewTournamentsDiscoveredEvent, TournamentAlertTriggeredEvent
from .bot import PokerBot, create_bot, run_bot
from .container import AppContainer

__version__ = "2.0.0"

__all__ = [
    "Settings",
    "get_settings",
    "I18nService",
    "t",
    "Tournament",
    "Prize",
    "PokerRoom",
    "BaseScraper",
    "FreeRollPasswordScraper",
    "FreerollPassScraper",
    "ScraperManager",
    "HttpFetcher",
    "Database",
    "EventRepository",
    "TournamentService",
    "AlertService",
    "EventBus",
    "Event",
    "NewTournamentsDiscoveredEvent",
    "TournamentAlertTriggeredEvent",
    "PokerBot",
    "create_bot",
    "run_bot",
    "AppContainer",
]
