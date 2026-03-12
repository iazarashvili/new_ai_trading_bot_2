from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    ticket: int
    symbol: str
    direction: str
    entry_price: float
    exit_price: float
    volume: float
    pnl: float
    entry_time: float
    exit_time: float
    duration_seconds: float = 0.0
    reasons: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.duration_seconds == 0.0 and self.exit_time > self.entry_time:
            self.duration_seconds = self.exit_time - self.entry_time


class TradeStatistics:
    """Accumulate closed trade records and produce summary statistics."""

    def __init__(self) -> None:
        self._records: List[TradeRecord] = []

    def record(self, trade: TradeRecord) -> None:
        self._records.append(trade)
        logger.info(
            "Trade recorded: %s %s pnl=%.2f (ticket %d)",
            trade.direction, trade.symbol, trade.pnl, trade.ticket,
        )

    @property
    def all_trades(self) -> List[TradeRecord]:
        return list(self._records)

    @property
    def pnls(self) -> List[float]:
        return [t.pnl for t in self._records]

    def by_symbol(self, symbol: str) -> List[TradeRecord]:
        return [t for t in self._records if t.symbol == symbol]

    def summary(self) -> Dict[str, object]:
        if not self._records:
            return {"total_trades": 0}

        wins = [t for t in self._records if t.pnl > 0]
        losses = [t for t in self._records if t.pnl <= 0]
        durations = [t.duration_seconds for t in self._records if t.duration_seconds > 0]

        return {
            "total_trades": len(self._records),
            "winners": len(wins),
            "losers": len(losses),
            "total_pnl": round(sum(t.pnl for t in self._records), 2),
            "avg_duration_minutes": round(
                (sum(durations) / len(durations) / 60) if durations else 0, 1
            ),
            "symbols": list({t.symbol for t in self._records}),
        }
