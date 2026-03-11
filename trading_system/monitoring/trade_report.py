from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Any, Optional

from trading_system.connectors.mt5_connector import MT5Connector

logger = logging.getLogger(__name__)

REPORT_DIR = Path(__file__).resolve().parent.parent.parent / "trade_reports"


class TradeReport:
    """Log individual trades and write end-of-day summaries."""

    def __init__(self, connector: MT5Connector) -> None:
        self._connector = connector
        REPORT_DIR.mkdir(exist_ok=True)

    def _today_path(self) -> Path:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return REPORT_DIR / f"{today}.txt"

    def log_trade(
        self,
        symbol: str,
        direction: str,
        price: float,
        sl: float,
        tp: float,
        volume: float,
        retcode: int,
        comment: str,
        reasons: Optional[List[str]] = None,
    ) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        reasons_str = ", ".join(reasons) if reasons else ""
        line = (
            f"[{timestamp}]  {symbol:<12} {direction:<5} "
            f"Price={price:<12.5f} SL={sl:<12.5f} TP={tp:<12.5f} "
            f"Lot={volume:<6.2f} Result={comment} (code={retcode}) "
            f"Reasons=[{reasons_str}]\n"
        )
        with open(self._today_path(), "a", encoding="utf-8") as f:
            f.write(line)

    def write_daily_summary(self) -> None:
        account = self._connector.account_info()
        if account is None:
            logger.warning("Cannot get account info for daily summary")
            return

        deals = self._connector.get_today_deals()

        closed_profit = 0.0
        wins = 0
        losses = 0
        closed_trades = 0

        for d in deals:
            if d.entry != 1:
                continue
            pnl = d.profit + d.swap + d.commission
            closed_profit += pnl
            closed_trades += 1
            if pnl > 0:
                wins += 1
            elif pnl < 0:
                losses += 1

        win_rate = (wins / closed_trades * 100) if closed_trades > 0 else 0.0

        positions = self._connector.get_open_positions()
        floating_pnl = sum(p.profit for p in positions)

        sent, success = self._count_today_orders()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        summary = (
            f"\n{'=' * 55}\n"
            f"  Daily Report  {today}\n"
            f"{'=' * 55}\n"
            f"  Balance:          ${account.balance:,.2f}\n"
            f"  Equity:           ${account.equity:,.2f}\n"
            f"{'-' * 55}\n"
            f"  Orders sent:      {sent}  (successful: {success})\n"
            f"  Closed trades:    {closed_trades}  (Win: {wins} | Loss: {losses})\n"
            f"  Win Rate:         {win_rate:.1f}%\n"
            f"  Closed P/L:      ${closed_profit:+,.2f}\n"
            f"{'-' * 55}\n"
            f"  Open positions:   {len(positions)}\n"
            f"  Floating P/L:    ${floating_pnl:+,.2f}\n"
            f"  Total daily P/L: ${closed_profit + floating_pnl:+,.2f}\n"
            f"{'=' * 55}\n"
        )

        with open(self._today_path(), "a", encoding="utf-8") as f:
            f.write(summary)

        logger.info(summary)

    def _count_today_orders(self) -> tuple[int, int]:
        filepath = self._today_path()
        if not filepath.exists():
            return 0, 0
        sent = 0
        success = 0
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("["):
                    sent += 1
                    if "code=10009" in line:
                        success += 1
        return sent, success
