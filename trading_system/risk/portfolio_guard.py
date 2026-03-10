from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Optional

from trading_system.config.risk_limits import RISK_LIMITS, RiskLimits
from trading_system.connectors.mt5_connector import MT5Connector
from trading_system.risk.risk_manager import RiskManager

logger = logging.getLogger(__name__)

SECONDS_PER_DAY = 86_400
SECONDS_PER_WEEK = 604_800


@dataclass
class PnLRecord:
    timestamp: float
    pnl: float
    balance_at_time: float


class PortfolioGuard:
    """Monitor rolling P&L and disable trading if daily/weekly loss limits are breached."""

    def __init__(
        self,
        connector: MT5Connector,
        risk_manager: RiskManager,
        limits: Optional[RiskLimits] = None,
    ) -> None:
        self._connector = connector
        self._risk_manager = risk_manager
        self._limits = limits or RISK_LIMITS
        self._pnl_records: Deque[PnLRecord] = deque(maxlen=5000)
        self._last_equity: Optional[float] = None

    def record_pnl(self, pnl: float, balance: float) -> None:
        self._pnl_records.append(PnLRecord(
            timestamp=time.time(), pnl=pnl, balance_at_time=balance,
        ))

    def check(self) -> None:
        account = self._connector.account_info()
        if account is None:
            return

        now = time.time()
        daily_pnl = sum(
            r.pnl for r in self._pnl_records if now - r.timestamp < SECONDS_PER_DAY
        )
        weekly_pnl = sum(
            r.pnl for r in self._pnl_records if now - r.timestamp < SECONDS_PER_WEEK
        )

        daily_loss_pct = abs(daily_pnl) / account.balance * 100 if daily_pnl < 0 else 0
        weekly_loss_pct = abs(weekly_pnl) / account.balance * 100 if weekly_pnl < 0 else 0

        if daily_loss_pct >= self._limits.max_daily_loss_pct:
            self._risk_manager.disable_trading(
                f"Daily loss {daily_loss_pct:.2f}% exceeds limit {self._limits.max_daily_loss_pct}%"
            )
        elif weekly_loss_pct >= self._limits.max_weekly_loss_pct:
            self._risk_manager.disable_trading(
                f"Weekly loss {weekly_loss_pct:.2f}% exceeds limit {self._limits.max_weekly_loss_pct}%"
            )

        self._last_equity = account.equity
