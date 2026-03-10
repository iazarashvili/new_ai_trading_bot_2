from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from trading_system.analytics.performance_metrics import Metrics, PerformanceMetrics
from trading_system.backtesting.backtester import BacktestConfig, BacktestResult, Backtester

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardWindow:
    in_sample_start: int
    in_sample_end: int
    out_of_sample_start: int
    out_of_sample_end: int
    in_sample_metrics: Metrics
    out_of_sample_metrics: Metrics


@dataclass
class WalkForwardResult:
    windows: List[WalkForwardWindow]
    aggregate_oos_metrics: Metrics


class WalkForward:
    """Walk-forward analysis: split data into rolling in-sample / out-of-sample
    windows and evaluate strategy robustness across regimes."""

    def __init__(
        self,
        n_splits: int = 5,
        oos_ratio: float = 0.2,
        config: Optional[BacktestConfig] = None,
    ) -> None:
        self._n_splits = n_splits
        self._oos_ratio = oos_ratio
        self._config = config or BacktestConfig()
        self._perf = PerformanceMetrics()

    def run(
        self,
        data: Dict[str, pd.DataFrame],
        execution_tf: str = "M5",
        htf: str = "D1",
    ) -> WalkForwardResult:
        exec_df = data[execution_tf]
        total = len(exec_df)
        step = total // self._n_splits
        oos_size = max(int(step * self._oos_ratio), 50)

        windows: List[WalkForwardWindow] = []
        all_oos_pnls: List[float] = []

        for i in range(self._n_splits):
            is_start = 0
            is_end = (i + 1) * step - oos_size
            oos_start = is_end
            oos_end = min((i + 1) * step, total)

            if is_end <= 200 or oos_end <= oos_start:
                continue

            is_data = {tf: df.iloc[is_start:is_end] for tf, df in data.items()}
            oos_data = {tf: df.iloc[oos_start:oos_end] for tf, df in data.items()}

            backtester = Backtester(self._config)

            try:
                is_result = backtester.run(is_data, execution_tf, htf, warmup=min(200, is_end // 2))
                oos_result = backtester.run(oos_data, execution_tf, htf, warmup=min(100, (oos_end - oos_start) // 2))
            except Exception:
                logger.exception("Walk-forward window %d failed", i)
                continue

            oos_pnls = [t.pnl for t in oos_result.trades]
            all_oos_pnls.extend(oos_pnls)

            windows.append(WalkForwardWindow(
                in_sample_start=is_start,
                in_sample_end=is_end,
                out_of_sample_start=oos_start,
                out_of_sample_end=oos_end,
                in_sample_metrics=is_result.metrics,
                out_of_sample_metrics=oos_result.metrics,
            ))

            logger.info(
                "WF window %d: IS trades=%d pf=%.2f | OOS trades=%d pf=%.2f",
                i,
                is_result.metrics.total_trades,
                is_result.metrics.profit_factor,
                oos_result.metrics.total_trades,
                oos_result.metrics.profit_factor,
            )

        aggregate = self._perf.calculate(all_oos_pnls, self._config.initial_balance)
        return WalkForwardResult(windows=windows, aggregate_oos_metrics=aggregate)
