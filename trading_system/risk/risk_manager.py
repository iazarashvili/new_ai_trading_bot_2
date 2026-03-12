from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Dict, Optional

from trading_system.config.risk_limits import RISK_LIMITS, RiskLimits, SYMBOL_SL_OVERRIDES
from trading_system.config.settings import SETTINGS
from trading_system.connectors.mt5_connector import MT5Connector
from trading_system.config.symbols import get_symbol_spec
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

    def _get_pip_value(self, symbol: str) -> float:
        try:
            return get_symbol_spec(symbol).pip_value
        except ValueError:
            return 0.0001

    def allow_trade(
        self,
        symbol: str,
        direction: str,
        entry: float,
        stop_loss: float,
    ) -> bool:
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
        if len(positions) >= self._limits.max_open_trades:
            logger.info("Trade blocked – max open trades (%d) reached", self._limits.max_open_trades)
            return False

        if any(p.symbol == symbol for p in positions):
            logger.info("Trade blocked – already in position for %s", symbol)
            return False

        sl_distance = abs(entry - stop_loss)
        pip_value = self._get_pip_value(symbol)
        overrides = SYMBOL_SL_OVERRIDES.get(symbol, {})
        min_sl_pips = overrides.get("min_sl_pips", self._limits.min_sl_pips)
        min_sl_spread_mult = overrides.get("min_sl_spread_mult", self._limits.min_sl_spread_mult)

        min_sl_distance = min_sl_pips * pip_value
        if sl_distance < min_sl_distance:
            logger.info(
                "Trade blocked – SL too tight (%s: %.5f < %.5f min)",
                symbol, sl_distance, min_sl_distance,
            )
            return False

        tick = self._connector.get_tick(symbol)
        if tick is not None:
            spread = (tick["ask"] - tick["bid"])
            min_vs_spread = spread * min_sl_spread_mult
            if sl_distance < min_vs_spread:
                logger.info(
                    "Trade blocked – SL too tight vs spread (%s: %.5f < %.5f)",
                    symbol, sl_distance, min_vs_spread,
                )
                return False

        last_close = self._last_close_time.get(symbol)
        if last_close is not None:
            elapsed_min = (time.time() - last_close) / 60.0
            if elapsed_min < self._limits.cooldown_minutes:
                logger.info("Trade blocked – cooldown (%s: %.0f min left)", symbol, self._limits.cooldown_minutes - elapsed_min)
                return False

        return True

    def record_close(self, symbol: str) -> None:
        self._last_close_time[symbol] = time.time()
