"""Lightweight asynchronous In-Memory EventBus for event-driven pub/sub."""

import asyncio
from typing import Dict, List, Type, Callable, Any, Coroutine, TypeVar
from .events import Event
from ..utils.logger import log

T = TypeVar("T", bound=Event)
EventHandler = Callable[[Any], Coroutine[Any, Any, None]]


class EventBus:
    """In-memory publish/subscribe event bus."""

    def __init__(self):
        self._subscribers: Dict[Type[Event], List[EventHandler]] = {}

    def subscribe(self, event_type: Type[T], handler: EventHandler):
        """Register an async handler for a specific event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: Type[T], handler: EventHandler):
        """Unregister an async handler."""
        if event_type in self._subscribers and handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)

    def clear(self):
        """Remove all subscribers (useful for testing)."""
        self._subscribers.clear()

    async def publish(self, event: Event):
        """
        Publish an event to all subscribed listeners concurrently and resiliently.
        """
        event_cls = type(event)
        handlers = list(self._subscribers.get(event_cls, []))

        # Also notify listeners subscribed to base Event class
        if event_cls is not Event and Event in self._subscribers:
            handlers.extend(self._subscribers[Event])

        if not handlers:
            return

        tasks = []
        for handler in handlers:
            try:
                tasks.append(handler(event))
            except Exception as e:
                log.error(f"Error invoking handler {handler} for {event_cls.__name__}: {e}")

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for handler, res in zip(handlers, results):
                if isinstance(res, Exception):
                    handler_name = handler.__name__ if hasattr(handler, "__name__") else str(handler)
                    log.error(
                        f"Event handler '{handler_name}' failed processing {event_cls.__name__}: {res}",
                        exc_info=res,
                    )
