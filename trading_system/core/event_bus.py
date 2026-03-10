from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class EventType(Enum):
    MARKET_DATA = auto()
    SIGNAL = auto()
    ORDER = auto()
    TRADE = auto()
    RISK = auto()
    POSITION_UPDATE = auto()
    SYSTEM = auto()


@dataclass
class Event:
    event_type: EventType
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[float] = None


Handler = Callable[[Event], None]


class EventBus:
    """Publish / subscribe event bus for decoupled component communication."""

    def __init__(self) -> None:
        self._subscribers: Dict[EventType, List[Handler]] = defaultdict(list)
        self._event_log: List[Event] = []

    def subscribe(self, event_type: EventType, handler: Handler) -> None:
        self._subscribers[event_type].append(handler)
        logger.debug("Subscribed %s to %s", handler.__qualname__, event_type.name)

    def publish(self, event: Event) -> None:
        import time

        if event.timestamp is None:
            event.timestamp = time.time()
        self._event_log.append(event)
        for handler in self._subscribers.get(event.event_type, []):
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "Handler %s failed for event %s",
                    handler.__qualname__,
                    event.event_type.name,
                )

    @property
    def history(self) -> List[Event]:
        return list(self._event_log)
