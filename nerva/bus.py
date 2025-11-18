# nerva/bus.py
from __future__ import annotations
from typing import Callable, Dict, List
import logging
from .types import Event, EventType


logger = logging.getLogger(__name__)


class EventBus:
    """
    Central pub/sub event bus for NERVA.
    Keeps agents decoupled and prevents callback hell.
    """

    def __init__(self) -> None:
        self._subscribers: Dict[EventType, List[Callable[[Event], None]]] = {}
        self._event_history: List[Event] = []
        self._max_history = 1000

    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """Register a handler for a specific event type."""
        self._subscribers.setdefault(event_type, []).append(handler)
        logger.debug(f"Subscribed handler to {event_type.name}")

    def unsubscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """Remove a handler from an event type."""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
                logger.debug(f"Unsubscribed handler from {event_type.name}")
            except ValueError:
                pass

    def publish(self, event: Event) -> None:
        """Publish an event to all registered handlers."""
        logger.info(f"Publishing event: {event.type.name} (id={event.id[:8]}...)")

        # Store in history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)

        # Dispatch to handlers
        handlers = self._subscribers.get(event.type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Handler error for {event.type.name}: {e}", exc_info=True)

    def get_history(self, limit: int = 100) -> List[Event]:
        """Retrieve recent event history."""
        return self._event_history[-limit:]
