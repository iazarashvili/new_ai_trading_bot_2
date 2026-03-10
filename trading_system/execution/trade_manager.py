from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from trading_system.connectors.mt5_connector import MT5Connector
from trading_system.core.event_bus import Event, EventBus, EventType
from trading_system.risk.portfolio_guard import PortfolioGuard

logger = logging.getLogger(__name__)


@dataclass
class ManagedTrade:
    ticket: int
    symbol: str
    direction: str
    entry_price: float
    initial_sl: float
    initial_tp: float
    volume: float
    current_sl: float = 0.0
    breakeven_set: bool = False
    partial_taken: bool = False
    trailing_active: bool = False

    def __post_init__(self) -> None:
        if self.current_sl == 0.0:
            self.current_sl = self.initial_sl

    @property
    def risk_distance(self) -> float:
        return abs(self.entry_price - self.initial_sl)


class TradeManager:
    """Manage open trades: breakeven, partial profit, and trailing stop.

    1R -> move SL to breakeven
    2R -> partial take profit (close 50%)
    3R -> trail stop behind structure
    """

    def __init__(
        self,
        connector: MT5Connector,
        event_bus: EventBus,
        portfolio_guard: PortfolioGuard,
    ) -> None:
        self._connector = connector
        self._event_bus = event_bus
        self._portfolio_guard = portfolio_guard
        self._trades: Dict[int, ManagedTrade] = {}

    def register_trade(self, trade: ManagedTrade) -> None:
        self._trades[trade.ticket] = trade
        logger.info("Registered trade %d for management", trade.ticket)

    def manage_open_trades(self, symbol: Optional[str] = None) -> None:
        self._portfolio_guard.check()

        positions = self._connector.get_open_positions(symbol)
        open_tickets = {p.ticket for p in positions}

        closed = [t for t in self._trades if t not in open_tickets]
        for ticket in closed:
            trade = self._trades.pop(ticket)
            logger.info("Trade %d closed externally", ticket)
            self._event_bus.publish(Event(
                event_type=EventType.TRADE,
                payload={"ticket": ticket, "symbol": trade.symbol, "action": "closed"},
            ))

        for pos in positions:
            trade = self._trades.get(pos.ticket)
            if trade is None:
                continue
            current_price = pos.price_current
            self._apply_management(trade, current_price)

    def _apply_management(self, trade: ManagedTrade, current_price: float) -> None:
        r = trade.risk_distance
        if r == 0:
            return

        if trade.direction == "BUY":
            pnl_r = (current_price - trade.entry_price) / r
        else:
            pnl_r = (trade.entry_price - current_price) / r

        if pnl_r >= 1.0 and not trade.breakeven_set:
            self._move_to_breakeven(trade)

        if pnl_r >= 2.0 and not trade.partial_taken:
            self._take_partial(trade)

        if pnl_r >= 3.0 and not trade.trailing_active:
            self._activate_trailing(trade, current_price)
        elif trade.trailing_active:
            self._update_trailing(trade, current_price)

    def _move_to_breakeven(self, trade: ManagedTrade) -> None:
        spread_buffer = trade.risk_distance * 0.05
        if trade.direction == "BUY":
            new_sl = trade.entry_price + spread_buffer
        else:
            new_sl = trade.entry_price - spread_buffer

        if self._connector.modify_position(trade.ticket, trade.symbol, new_sl, trade.initial_tp):
            trade.current_sl = new_sl
            trade.breakeven_set = True
            logger.info("Trade %d – SL moved to breakeven (%.5f)", trade.ticket, new_sl)

    def _take_partial(self, trade: ManagedTrade) -> None:
        close_volume = round(trade.volume * 0.5, 2)
        if close_volume <= 0:
            return
        if self._connector.close_position(trade.ticket, trade.symbol, close_volume):
            trade.partial_taken = True
            trade.volume -= close_volume
            logger.info("Trade %d – partial close %.2f lots", trade.ticket, close_volume)

            account = self._connector.account_info()
            if account:
                self._portfolio_guard.record_pnl(0.0, account.balance)

    def _activate_trailing(self, trade: ManagedTrade, current_price: float) -> None:
        trade.trailing_active = True
        self._update_trailing(trade, current_price)
        logger.info("Trade %d – trailing stop activated", trade.ticket)

    def _update_trailing(self, trade: ManagedTrade, current_price: float) -> None:
        trail_distance = trade.risk_distance * 1.5
        if trade.direction == "BUY":
            new_sl = current_price - trail_distance
            if new_sl > trade.current_sl:
                self._connector.modify_position(trade.ticket, trade.symbol, new_sl, trade.initial_tp)
                trade.current_sl = new_sl
        else:
            new_sl = current_price + trail_distance
            if new_sl < trade.current_sl:
                self._connector.modify_position(trade.ticket, trade.symbol, new_sl, trade.initial_tp)
                trade.current_sl = new_sl
