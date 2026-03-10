from __future__ import annotations

import logging
import time
from typing import Dict, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class DataCache:
    """In-memory cache for OHLCV DataFrames with TTL-based expiry."""

    def __init__(self, ttl_seconds: int = 60) -> None:
        self._ttl = ttl_seconds
        self._store: Dict[str, Tuple[float, pd.DataFrame]] = {}

    def _key(self, symbol: str, timeframe: str) -> str:
        return f"{symbol}_{timeframe}"

    def get(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        key = self._key(symbol, timeframe)
        entry = self._store.get(key)
        if entry is None:
            return None
        ts, df = entry
        if time.time() - ts > self._ttl:
            del self._store[key]
            return None
        return df

    def put(self, symbol: str, timeframe: str, df: pd.DataFrame) -> None:
        key = self._key(symbol, timeframe)
        self._store[key] = (time.time(), df)

    def invalidate(self, symbol: str, timeframe: str) -> None:
        key = self._key(symbol, timeframe)
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()
