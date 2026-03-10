from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Metrics:
    total_trades: int
    winners: int
    losers: int
    win_rate: float
    profit_factor: float
    total_pnl: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    avg_win: float
    avg_loss: float
    expectancy: float


class PerformanceMetrics:
    """Calculate institutional-grade performance metrics from a list of trade P&Ls."""

    def __init__(self, risk_free_rate: float = 0.0) -> None:
        self._rf = risk_free_rate

    def calculate(self, pnls: List[float], initial_balance: float = 10_000.0) -> Metrics:
        if not pnls:
            return self._empty_metrics()

        arr = np.array(pnls, dtype=float)
        wins = arr[arr > 0]
        losses = arr[arr < 0]

        total = len(arr)
        n_wins = len(wins)
        n_losses = len(losses)
        win_rate = n_wins / total if total > 0 else 0.0

        gross_profit = float(wins.sum()) if len(wins) else 0.0
        gross_loss = float(abs(losses.sum())) if len(losses) else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        avg_win = float(wins.mean()) if len(wins) else 0.0
        avg_loss = float(losses.mean()) if len(losses) else 0.0
        expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss

        equity_curve = np.cumsum(arr) + initial_balance
        max_dd, max_dd_pct = self._max_drawdown(equity_curve)

        sharpe = self._sharpe_ratio(arr)

        return Metrics(
            total_trades=total,
            winners=n_wins,
            losers=n_losses,
            win_rate=round(win_rate, 4),
            profit_factor=round(profit_factor, 4),
            total_pnl=round(float(arr.sum()), 2),
            max_drawdown=round(max_dd, 2),
            max_drawdown_pct=round(max_dd_pct, 4),
            sharpe_ratio=round(sharpe, 4),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            expectancy=round(expectancy, 2),
        )

    @staticmethod
    def _max_drawdown(equity: np.ndarray) -> tuple[float, float]:
        peak = np.maximum.accumulate(equity)
        drawdown = peak - equity
        max_dd = float(drawdown.max())
        max_dd_pct = float((drawdown / peak).max()) if peak.max() > 0 else 0.0
        return max_dd, max_dd_pct

    def _sharpe_ratio(self, returns: np.ndarray) -> float:
        if len(returns) < 2:
            return 0.0
        std = float(returns.std())
        if std == 0:
            return 0.0
        mean_r = float(returns.mean())
        return (mean_r - self._rf) / std * np.sqrt(252)

    @staticmethod
    def _empty_metrics() -> Metrics:
        return Metrics(
            total_trades=0, winners=0, losers=0, win_rate=0.0,
            profit_factor=0.0, total_pnl=0.0, max_drawdown=0.0,
            max_drawdown_pct=0.0, sharpe_ratio=0.0, avg_win=0.0,
            avg_loss=0.0, expectancy=0.0,
        )
