from __future__ import annotations

import logging
import time
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

Task = Callable[[], None]


class Scheduler:
    """Simple interval-based task scheduler for the main trading loop."""

    def __init__(self, interval_seconds: float = 5.0) -> None:
        self._interval = interval_seconds
        self._tasks: List[Task] = []
        self._running = False

    def register(self, task: Task) -> None:
        self._tasks.append(task)
        logger.debug("Registered task: %s", task.__qualname__)

    def start(self) -> None:
        self._running = True
        logger.info("Scheduler started – interval %.1fs", self._interval)
        while self._running:
            cycle_start = time.time()
            for task in self._tasks:
                if not self._running:
                    break
                try:
                    task()
                except Exception:
                    logger.exception("Task %s raised an exception", task.__qualname__)
            elapsed = time.time() - cycle_start
            sleep_time = max(0.0, self._interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)

    def stop(self) -> None:
        self._running = False
        logger.info("Scheduler stopped")
