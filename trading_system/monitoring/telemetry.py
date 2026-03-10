from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List

logger = logging.getLogger(__name__)


@dataclass
class CycleMetric:
    timestamp: float
    duration_ms: float
    symbol: str
    signals_generated: int
    errors: int


class Telemetry:
    """Lightweight system health telemetry collector."""

    def __init__(self, max_history: int = 5000) -> None:
        self._max_history = max_history
        self._metrics: List[CycleMetric] = []
        self._error_counts: Dict[str, int] = {}

    def record_cycle(
        self,
        symbol: str,
        duration_ms: float,
        signals: int = 0,
        errors: int = 0,
    ) -> None:
        metric = CycleMetric(
            timestamp=time.time(),
            duration_ms=duration_ms,
            symbol=symbol,
            signals_generated=signals,
            errors=errors,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_history:
            self._metrics = self._metrics[-self._max_history:]

    def record_error(self, component: str) -> None:
        self._error_counts[component] = self._error_counts.get(component, 0) + 1

    @property
    def avg_cycle_ms(self) -> float:
        if not self._metrics:
            return 0.0
        return sum(m.duration_ms for m in self._metrics) / len(self._metrics)

    @property
    def total_errors(self) -> int:
        return sum(self._error_counts.values())

    def summary(self) -> Dict[str, object]:
        return {
            "cycles_recorded": len(self._metrics),
            "avg_cycle_ms": round(self.avg_cycle_ms, 2),
            "total_errors": self.total_errors,
            "error_breakdown": dict(self._error_counts),
        }
