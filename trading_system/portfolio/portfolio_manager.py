from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from trading_system.connectors.mt5_connector import AccountInfo, MT5Connector

logger = logging.getLogger(__name__)


@dataclass
class PortfolioSnapshot:
    balance: float
    equity: float
    margin_used: float
    free_margin: float
    open_positions: int
    unrealized_pnl: float
    symbols_exposed: List[str]


class PortfolioManager:
    """Track overall portfolio state and provide a snapshot for decision-making."""

    def __init__(self, connector: MT5Connector) -> None:
        self._connector = connector
        self._snapshots: List[PortfolioSnapshot] = []

    def snapshot(self) -> Optional[PortfolioSnapshot]:
        account = self._connector.account_info()
        if account is None:
            return None

        positions = self._connector.get_open_positions()
        symbols = list({p.symbol for p in positions})
        unrealized = sum(p.profit for p in positions) if positions else 0.0

        snap = PortfolioSnapshot(
            balance=account.balance,
            equity=account.equity,
            margin_used=account.margin,
            free_margin=account.free_margin,
            open_positions=len(positions),
            unrealized_pnl=unrealized,
            symbols_exposed=symbols,
        )
        self._snapshots.append(snap)
        return snap

    @property
    def history(self) -> List[PortfolioSnapshot]:
        return list(self._snapshots)
