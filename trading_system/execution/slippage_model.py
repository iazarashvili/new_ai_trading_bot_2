from __future__ import annotations

import logging
from typing import Optional

from trading_system.connectors.mt5_connector import MT5Connector

logger = logging.getLogger(__name__)


class SlippageModel:
    """Estimate and protect against slippage.

    Computes the current spread and compares to a threshold to decide
    whether execution conditions are acceptable.
    """

    def __init__(self, max_spread_atr_ratio: float = 0.3) -> None:
        self._max_ratio = max_spread_atr_ratio

    def current_spread(self, connector: MT5Connector, symbol: str) -> Optional[float]:
        tick = connector.get_tick(symbol)
        if tick is None:
            return None
        return tick["ask"] - tick["bid"]

    def acceptable(
        self, connector: MT5Connector, symbol: str, atr: float
    ) -> bool:
        spread = self.current_spread(connector, symbol)
        if spread is None:
            logger.warning("Cannot get spread for %s – assuming acceptable", symbol)
            return True
        if atr <= 0:
            return True
        ratio = spread / atr
        ok = ratio <= self._max_ratio
        if not ok:
            logger.info(
                "Spread/ATR ratio %.3f exceeds %.3f for %s – blocking execution",
                ratio, self._max_ratio, symbol,
            )
        return ok
