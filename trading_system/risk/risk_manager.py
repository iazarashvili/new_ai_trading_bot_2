from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Dict, Optional

from trading_system.config.risk_limits import RISK_LIMITS, RiskLimits
from trading_system.config.settings import SETTINGS
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

    def _is_within_trading_hours(self) -> bool:
        """Check if current local time is within allowed trading hours."""
        hours_cfg = SETTINGS.trading_hours
        if not hours_cfg.enabled:
            return True
        current_hour = datetime.now().hour
        return hours_cfg.start_hour <= current_hour < hours_cfg.end_hour

    def allow_trade(self, symbol: str, direction: str, stop_loss: float) -> bool:
        if self._trading_disabled:
            logger.info("Trade blocked – trading disabled")
            return False

        if not self._is_within_trading_hours():
            logger.info(
                "Trade blocked – outside trading hours (allowed %02d:00–%02d:00)",
                SETTINGS.trading_hours.start_hour,
                SETTINGS.trading_hours.end_hour,
            )
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
