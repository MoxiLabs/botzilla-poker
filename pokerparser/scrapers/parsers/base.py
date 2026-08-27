"""Abstract Base HTML Parser for poker freeroll sources."""

from abc import ABC, abstractmethod
from typing import List
from ...domain.models import Tournament


class BaseHtmlParser(ABC):
    """Pure parser interface: accepts raw HTML and returns domain Tournaments."""

    def __init__(self, base_url: str, timezone: str = "Europe/Budapest"):
        self.base_url = base_url
        self.timezone = timezone

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Domain or identifier of the source."""
        pass

    @abstractmethod
    def parse(self, html_content: str) -> List[Tournament]:
        """Extracts Tournament events from HTML content without any network calls."""
        pass
