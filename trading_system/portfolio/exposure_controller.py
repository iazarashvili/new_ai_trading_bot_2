from __future__ import annotations

import logging
from typing import Optional

from trading_system.config.risk_limits import RISK_LIMITS, RiskLimits
from trading_system.connectors.mt5_connector import MT5Connector

logger = logging.getLogger(__name__)


class ExposureController:
    """Enforce per-symbol and overall portfolio exposure limits."""

    def __init__(
        self,
        connector: MT5Connector,
        limits: Optional[RiskLimits] = None,
    ) -> None:
        self._connector = connector
        self._limits = limits or RISK_LIMITS

    def can_open(self, symbol: str) -> bool:
        positions = self._connector.get_open_positions()
        if len(positions) >= self._limits.max_open_trades:
            logger.info("Exposure check: max open trades reached")
            return False

        symbol_positions = [p for p in positions if p.symbol == symbol]
        if symbol_positions:
            logger.info("Exposure check: already exposed to %s", symbol)
            return False

        return True

    def current_exposure(self) -> dict:
        positions = self._connector.get_open_positions()
        exposure: dict = {}
        for p in positions:
            if p.symbol not in exposure:
                exposure[p.symbol] = {"count": 0, "volume": 0.0, "pnl": 0.0}
            exposure[p.symbol]["count"] += 1
            exposure[p.symbol]["volume"] += p.volume
            exposure[p.symbol]["pnl"] += p.profit
        return exposure
