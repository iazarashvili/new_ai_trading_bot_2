from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from trading_system.connectors.mt5_connector import MT5Connector, OrderResult
from trading_system.core.event_bus import Event, EventBus, EventType
from trading_system.execution.slippage_model import SlippageModel
from trading_system.execution.trade_manager import ManagedTrade, TradeManager
from trading_system.monitoring.trade_report import TradeReport
from trading_system.risk.position_sizer import PositionSizer

if TYPE_CHECKING:
    from trading_system.strategy.signal_engine import Signal

logger = logging.getLogger(__name__)


class OrderExecutor:
    """Place orders via MT5 with slippage protection and position sizing."""

    def __init__(
        self,
        connector: MT5Connector,
        event_bus: EventBus,
        position_sizer: PositionSizer,
        slippage_model: SlippageModel,
        trade_manager: TradeManager,
        trade_report: TradeReport,
    ) -> None:
        self._connector = connector
        self._event_bus = event_bus
        self._sizer = position_sizer
        self._slippage = slippage_model
        self._trade_manager = trade_manager
        self._trade_report = trade_report

    def execute_signal(self, signal: "Signal") -> Optional[OrderResult]:
        account = self._connector.account_info()
        if account is None:
            logger.error("Cannot get account info – aborting execution")
            return None

        sl_distance = abs(signal.entry - signal.stop_loss)
        atr_estimate = sl_distance / 1.5
        if not self._slippage.acceptable(self._connector, signal.symbol, atr_estimate):
            logger.warning("Spread too wide for %s – skipping execution", signal.symbol)
            return None

        volume = self._sizer.calculate(account.balance, sl_distance, signal.symbol)
        if volume <= 0:
            logger.warning("Position size is zero for %s", signal.symbol)
            return None

        result = self._connector.place_order(
            symbol=signal.symbol,
            direction=signal.direction,
            volume=volume,
            price=signal.entry,
            sl=signal.stop_loss,
            tp=signal.take_profit,
            comment=f"sig_{signal.confidence:.0%}",
        )

        if result.success:
            self._event_bus.publish(Event(
                event_type=EventType.ORDER,
                payload={
                    "symbol": signal.symbol,
                    "direction": signal.direction,
                    "ticket": result.ticket,
                    "price": result.price,
                    "volume": result.volume,
                    "sl": signal.stop_loss,
                    "tp": signal.take_profit,
                },
            ))
            self._trade_manager.register_trade(ManagedTrade(
                ticket=result.ticket,
                symbol=signal.symbol,
                direction=signal.direction,
                entry_price=result.price,
                initial_sl=signal.stop_loss,
                initial_tp=signal.take_profit,
                volume=result.volume,
            ))
            logger.info(
                "EXECUTED %s %s %.2f lots @ %.5f  SL=%.5f TP=%.5f  reasons=%s",
                signal.direction, signal.symbol, result.volume,
                result.price, signal.stop_loss, signal.take_profit,
                signal.reasons,
            )

        self._trade_report.log_trade(
            symbol=signal.symbol,
            direction=signal.direction,
            price=result.price if result.success else signal.entry,
            sl=signal.stop_loss,
            tp=signal.take_profit,
            volume=result.volume if result.success else volume,
            retcode=result.retcode,
            comment=result.comment,
            reasons=signal.reasons,
        )

        if not result.success:
            logger.error(
                "EXECUTION FAILED for %s %s: %s (retcode=%d)",
                signal.direction, signal.symbol, result.comment, result.retcode,
            )

        return result
