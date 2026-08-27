"""Unit tests for EventBus pub/sub system."""

import asyncio
import unittest
from datetime import date, time
from pokerparser.events.bus import EventBus
from pokerparser.events.events import (
    Event,
    NewTournamentsDiscoveredEvent,
    TournamentAlertTriggeredEvent,
)
from pokerparser.domain.models import Tournament


class TestEventBus(unittest.IsolatedAsyncioTestCase):
    """Test suite verifying EventBus publish, subscribe, and exception handling."""

    async def asyncSetUp(self):
        self.bus = EventBus()

    def _create_sample_tournament(self) -> Tournament:
        return Tournament(
            name="Test Freeroll",
            room="PokerStars",
            date=date(2026, 8, 28),
            time=time(20, 0),
            is_all_day=False,
            prize="$100",
            password="test",
            source="test_source",
            url="https://example.com",
        )

    async def test_subscribe_and_publish_specific_event(self):
        """Test that subscribers receive matching events."""
        received = []

        async def handler(event: NewTournamentsDiscoveredEvent):
            received.append(event)

        self.bus.subscribe(NewTournamentsDiscoveredEvent, handler)

        event = NewTournamentsDiscoveredEvent(
            tournaments=[self._create_sample_tournament()],
            is_daily_summary=True,
        )
        await self.bus.publish(event)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0], event)

    async def test_unsubscribe(self):
        """Test unsubscribing a handler."""
        received = []

        async def handler(event: NewTournamentsDiscoveredEvent):
            received.append(event)

        self.bus.subscribe(NewTournamentsDiscoveredEvent, handler)
        self.bus.unsubscribe(NewTournamentsDiscoveredEvent, handler)

        event = NewTournamentsDiscoveredEvent(
            tournaments=[self._create_sample_tournament()],
            is_daily_summary=False,
        )
        await self.bus.publish(event)

        self.assertEqual(len(received), 0)

    async def test_resilient_handler_failure(self):
        """Test that an exception in one handler does not stop other handlers."""
        success_calls = []

        async def failing_handler(event: TournamentAlertTriggeredEvent):
            raise RuntimeError("Handler failed intentionally")

        async def successful_handler(event: TournamentAlertTriggeredEvent):
            success_calls.append(event)

        self.bus.subscribe(TournamentAlertTriggeredEvent, failing_handler)
        self.bus.subscribe(TournamentAlertTriggeredEvent, successful_handler)

        event = TournamentAlertTriggeredEvent(
            tournament=self._create_sample_tournament(),
            alert_type="urgent",
            minutes_left=10,
        )
        await self.bus.publish(event)

        self.assertEqual(len(success_calls), 1)
        self.assertEqual(success_calls[0], event)


if __name__ == "__main__":
    unittest.main()
