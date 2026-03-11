from __future__ import annotations

import logging
import time
from typing import Dict, Optional

from trading_system.config.risk_limits import RISK_LIMITS, RiskLimits
from trading_system.connectors.mt5_connector import MT5Connector
from trading_system.core.event_bus import Event, EventBus, EventType

logger = logging.getLogger(__name__)


class RiskManager:
    """Pre-trade risk gate – validates that a new trade is within limits."""

    def __init__(
        self,
        connector: MT5Connector,
        event_bus: EventBus,
        limits: Optional[RiskLimits] = None,
    ) -> None:
        self._connector = connector
        self._event_bus = event_bus
        self._limits = limits or RISK_LIMITS
        self._trading_disabled = False
        self._last_close_time: Dict[str, float] = {}

    @property
    def trading_disabled(self) -> bool:
        return self._trading_disabled

    def disable_trading(self, reason: str) -> None:
        self._trading_disabled = True
        logger.warning("TRADING DISABLED: %s", reason)
        self._event_bus.publish(Event(
            event_type=EventType.RISK,
            payload={"action": "disable_trading", "reason": reason},
        ))

    def enable_trading(self) -> None:
        self._trading_disabled = False
        logger.info("Trading re-enabled")

    def allow_trade(self, symbol: str, direction: str, stop_loss: float) -> bool:
        if self._trading_disabled:
            logger.info("Trade blocked – trading disabled")
            return False

        positions = self._connector.get_open_positions()

        if any(p.symbol == symbol for p in positions):
            return False

        last_close = self._last_close_time.get(symbol)
        if last_close is not None:
            elapsed_min = (time.time() - last_close) / 60.0
            if elapsed_min < self._limits.cooldown_minutes:
                return False

        return True

    def record_close(self, symbol: str) -> None:
        self._last_close_time[symbol] = time.time()
