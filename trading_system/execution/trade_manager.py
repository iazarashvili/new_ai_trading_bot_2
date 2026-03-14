from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

from trading_system.connectors.mt5_connector import MT5Connector
from trading_system.config.symbols import get_symbol_spec
from trading_system.core.event_bus import Event, EventBus, EventType
from trading_system.risk.portfolio_guard import PortfolioGuard
from trading_system.risk.risk_manager import RiskManager

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
    last_price: float = 0.0
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

    Fixes:
    - PnL calculation includes contract_size (critical for forex)
    - Trailing stop tightened from 1.5R to 1.0R
    """

    def __init__(
        self,
        connector: MT5Connector,
        event_bus: EventBus,
        portfolio_guard: PortfolioGuard,
        risk_manager: RiskManager,
    ) -> None:
        self._connector = connector
        self._event_bus = event_bus
        self._portfolio_guard = portfolio_guard
        self._risk_manager = risk_manager
        self._trades: Dict[int, ManagedTrade] = {}

    def register_trade(self, trade: ManagedTrade) -> None:
        self._trades[trade.ticket] = trade
        logger.info("Registered trade %d for management", trade.ticket)

    def manage_open_trades(self, symbol: Optional[str] = None) -> None:
        self._portfolio_guard.check()

        positions = self._connector.get_open_positions(symbol)
        open_tickets = {p.ticket for p in positions}

        closed = [
            t for t, trade in self._trades.items()
            if t not in open_tickets and (symbol is None or trade.symbol == symbol)
        ]
        for ticket in closed:
            trade = self._trades.pop(ticket)
            realized_pnl = self._calc_closed_pnl(trade)
            account = self._connector.account_info()
            if account:
                self._portfolio_guard.record_pnl(realized_pnl, account.balance)
            self._risk_manager.record_close(trade.symbol)
            logger.info("Trade %d closed (PnL=%.2f)", ticket, realized_pnl)
            self._event_bus.publish(Event(
                event_type=EventType.TRADE,
                payload={"ticket": ticket, "symbol": trade.symbol, "action": "closed", "pnl": realized_pnl},
            ))

        for pos in positions:
            trade = self._trades.get(pos.ticket)
            if trade is None:
                trade = self._adopt_position(pos)
            current_price = pos.price_current
            trade.last_price = current_price
            self._apply_management(trade, current_price)

    @staticmethod
    def _get_contract_size(symbol: str) -> float:
        try:
            return get_symbol_spec(symbol).contract_size
        except ValueError:
            return 1.0

    def _calc_closed_pnl(self, trade: ManagedTrade) -> float:
        """Estimate realized PnL from last known price.

        Fix: multiply by contract_size. For forex 1 lot = 100,000 units,
        so a 20-pip move on 0.5 lots = 0.0020 * 0.5 * 100,000 = $100.
        Previously this was 0.0020 * 0.5 = $0.001 (wrong by 100,000x).
        """
        close_price = trade.last_price if trade.last_price != 0.0 else trade.entry_price
        contract_size = self._get_contract_size(trade.symbol)
        if trade.direction == "BUY":
            return (close_price - trade.entry_price) * trade.volume * contract_size
        return (trade.entry_price - close_price) * trade.volume * contract_size

    def _adopt_position(self, pos) -> ManagedTrade:
        """Re-register an MT5 position not tracked in memory (e.g. after restart)."""
        direction = "BUY" if pos.type == 0 else "SELL"
        trade = ManagedTrade(
            ticket=pos.ticket,
            symbol=pos.symbol,
            direction=direction,
            entry_price=pos.price_open,
            initial_sl=pos.sl,
            initial_tp=pos.tp,
            volume=pos.volume,
            current_sl=pos.sl,
        )
        self._trades[pos.ticket] = trade
        logger.info(
            "Adopted orphan position %d (%s %s) opened @ %.5f",
            pos.ticket, direction, pos.symbol, pos.price_open,
        )
        return trade

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
        tick = self._connector.get_tick(trade.symbol)
        if tick is None:
            return
        current_price = tick["bid"] if trade.direction == "BUY" else tick["ask"]
        if self._connector.close_position(trade.ticket, trade.symbol, close_volume):
            trade.partial_taken = True
            trade.volume -= close_volume

            contract_size = self._get_contract_size(trade.symbol)
            if trade.direction == "BUY":
                partial_pnl = (current_price - trade.entry_price) * close_volume * contract_size
            else:
                partial_pnl = (trade.entry_price - current_price) * close_volume * contract_size

            account = self._connector.account_info()
            if account:
                self._portfolio_guard.record_pnl(partial_pnl, account.balance)
            logger.info("Trade %d – partial close %.2f lots (PnL=%.2f)", trade.ticket, close_volume, partial_pnl)

    def _activate_trailing(self, trade: ManagedTrade, current_price: float) -> None:
        trade.trailing_active = True
        self._update_trailing(trade, current_price)
        logger.info("Trade %d – trailing stop activated", trade.ticket)

    def _update_trailing(self, trade: ManagedTrade, current_price: float) -> None:
        # Tightened from 1.5R to 1.0R — keeps more profit on forex
        trail_distance = trade.risk_distance * 1.0
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
