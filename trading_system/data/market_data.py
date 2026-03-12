from __future__ import annotations

import logging
from typing import Dict, Optional

import pandas as pd

from trading_system.data.candle_service import CandleService

logger = logging.getLogger(__name__)


class MarketData:
    """High-level aggregator that provides candle data across all timeframes."""

    def __init__(
        self,
        candle_service: CandleService,
        timeframes: tuple[str, ...] = ("M15", "H1", "H4", "D1"),
    ) -> None:
        self._candle_service = candle_service
        self._timeframes = timeframes

    def snapshot(self, symbol: str) -> Dict[str, Optional[pd.DataFrame]]:
        result: Dict[str, Optional[pd.DataFrame]] = {}
        for tf in self._timeframes:
            result[tf] = self._candle_service.get_candles(symbol, tf)
        return result

    def refresh_all(self, symbol: str) -> Dict[str, Optional[pd.DataFrame]]:
        result: Dict[str, Optional[pd.DataFrame]] = {}
        for tf in self._timeframes:
            result[tf] = self._candle_service.refresh(symbol, tf)
        return result
