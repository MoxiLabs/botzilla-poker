"""Parsers package for HTML data extraction."""

from .base import BaseHtmlParser
from .freeroll_password import FreeRollPasswordParser
from .freerollpass import FreerollPassParser

__all__ = ["BaseHtmlParser", "FreeRollPasswordParser", "FreerollPassParser"]
