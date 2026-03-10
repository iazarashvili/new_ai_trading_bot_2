from __future__ import annotations

import logging
from typing import Optional

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
        if len(positions) >= self._limits.max_open_trades:
            logger.info(
                "Trade blocked – max open trades (%d) reached",
                self._limits.max_open_trades,
            )
            return False

        return True
