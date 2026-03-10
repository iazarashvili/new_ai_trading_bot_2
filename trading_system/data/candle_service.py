from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from trading_system.connectors.mt5_connector import MT5Connector
from trading_system.data.data_cache import DataCache

logger = logging.getLogger(__name__)


class CandleService:
    """Fetch and maintain a rolling window of OHLCV data per symbol / timeframe."""

    def __init__(
        self,
        connector: MT5Connector,
        cache: DataCache,
        rolling_window: int = 1000,
    ) -> None:
        self._connector = connector
        self._cache = cache
        self._rolling_window = rolling_window

    def get_candles(
        self, symbol: str, timeframe: str
    ) -> Optional[pd.DataFrame]:
        cached = self._cache.get(symbol, timeframe)
        if cached is not None:
            return cached

        df = self._connector.get_candles(symbol, timeframe, self._rolling_window)
        if df is not None and not df.empty:
            self._cache.put(symbol, timeframe, df)
            logger.debug(
                "Fetched %d candles for %s %s", len(df), symbol, timeframe
            )
        return df

    def refresh(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        self._cache.invalidate(symbol, timeframe)
        return self.get_candles(symbol, timeframe)
