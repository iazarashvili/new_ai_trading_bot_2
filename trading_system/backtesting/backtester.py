from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional
import pandas as pd

from trading_system.analytics.performance_metrics import Metrics, PerformanceMetrics
from trading_system.features.fair_value_gap import FairValueGap
from trading_system.features.liquidity_model import LiquidityModel
from trading_system.features.market_structure import MarketStructure, Trend
from trading_system.features.order_block_detector import OrderBlockDetector
from trading_system.features.support_resistance import SupportResistance
from trading_system.features.volatility_model import VolatilityModel

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    initial_balance: float = 10_000.0
    risk_per_trade_pct: float = 1.0
    max_open_trades: int = 1
    commission_per_lot: float = 0.0
    spread_points: float = 0.0


@dataclass
class BacktestTrade:
    entry_idx: int
    direction: str
    entry_price: float
    sl: float
    tp: float
    volume: float
    exit_idx: int = -1
    exit_price: float = 0.0
    pnl: float = 0.0
    closed: bool = False


@dataclass
class BacktestResult:
    metrics: Metrics
    trades: List[BacktestTrade]
    equity_curve: List[float]


class Backtester:
    """Historical simulation engine.

    Replays candle data bar-by-bar, applies the same feature detection
    and signal logic used in live mode, and tracks simulated trades.
    """

    def __init__(self, config: Optional[BacktestConfig] = None) -> None:
        self._config = config or BacktestConfig()
        self._market_structure = MarketStructure()
        self._liquidity_model = LiquidityModel()
        self._ob_detector = OrderBlockDetector()
        self._fvg_detector = FairValueGap()
        self._sr = SupportResistance()
        self._vol_model = VolatilityModel()
        self._perf = PerformanceMetrics()

    def run(
        self,
        data: Dict[str, pd.DataFrame],
        execution_tf: str = "M5",
        htf: str = "D1",
        warmup: int = 200,
        step: int = 1,
        htf_start_offset: int = 0,
    ) -> BacktestResult:
        exec_df = data.get(execution_tf)
        htf_df = data.get(htf)
        if exec_df is None:
            raise ValueError(f"No data for execution timeframe {execution_tf}")

        bars_per_day = 288 if execution_tf == "M5" else 96 if execution_tf == "M15" else 288
        balance = self._config.initial_balance
        trades: List[BacktestTrade] = []
        equity: List[float] = [balance]
        open_trade: Optional[BacktestTrade] = None

        htf_trend = Trend.NEUTRAL
        if htf_df is not None and len(htf_df) >= 20:
            day_at_warmup = (htf_start_offset + warmup) // bars_per_day + 1
            htf_warmup = max(20, min(day_at_warmup, len(htf_df)))
            htf_ms = self._market_structure.analyze(htf_df.iloc[:htf_warmup])
            htf_trend = htf_ms.trend

        for i in range(warmup, len(exec_df)):
            window = exec_df.iloc[max(0, i - 400) : i + 1]

            if open_trade is not None and not open_trade.closed:
                high = exec_df["high"].iloc[i]
                low = exec_df["low"].iloc[i]
                open_trade = self._check_exit(open_trade, high, low, i)
                if open_trade.closed:
                    balance += open_trade.pnl
                    trades.append(open_trade)
                    open_trade = None

            equity.append(balance + (self._unrealized(open_trade, exec_df["close"].iloc[i]) if open_trade else 0))

            if open_trade is not None:
                continue

            if i % step != 0:
                continue

            if len(window) < 50:
                continue

            # Periodically refresh HTF trend
            if htf_df is not None and i % 100 == 0:
                day_idx = (htf_start_offset + i) // bars_per_day + 1
                htf_window = htf_df.iloc[: min(len(htf_df), day_idx)]
                if len(htf_window) > 20:
                    htf_ms = self._market_structure.analyze(htf_window)
                    htf_trend = htf_ms.trend

            ms = self._market_structure.analyze(window)
            vol = self._vol_model.analyze(window)
            if not vol.tradeable:
                continue

            liq = self._liquidity_model.analyze(window)
            obs = self._ob_detector.detect(window)
            fvgs = self._fvg_detector.detect(window)

            close = float(exec_df["close"].iloc[i])
            signal = self._generate_signal(
                htf_trend, ms, liq, obs, fvgs, vol, close
            )
            if signal is None:
                continue

            direction, sl, tp = signal
            sl_dist = abs(close - sl)
            if sl_dist == 0:
                continue

            risk_amount = balance * (self._config.risk_per_trade_pct / 100.0)
            volume = risk_amount / sl_dist

            open_trade = BacktestTrade(
                entry_idx=i,
                direction=direction,
                entry_price=close,
                sl=sl,
                tp=tp,
                volume=volume,
            )

        if open_trade and not open_trade.closed:
            open_trade.exit_idx = len(exec_df) - 1
            open_trade.exit_price = float(exec_df["close"].iloc[-1])
            self._finalize_trade(open_trade)
            balance += open_trade.pnl
            trades.append(open_trade)
            equity.append(balance)

        pnls = [t.pnl for t in trades]
        metrics = self._perf.calculate(pnls, self._config.initial_balance)

        return BacktestResult(metrics=metrics, trades=trades, equity_curve=equity)

    def _generate_signal(
        self, htf_trend, ms, liq, obs, fvgs, vol, close
    ) -> Optional[tuple]:
        atr = vol.atr
        if atr <= 0 or atr < abs(close) * 0.0005:
            return None

        if htf_trend == Trend.BULLISH:
            has_sweep = any(s.close_back_inside and s.sweep_price < close for s in liq.sweeps)
            has_ob = any(ob.direction == "bullish" and not ob.mitigated and ob.low <= close <= ob.high for ob in obs)
            has_fvg = any(g.direction == "bullish" and not g.filled and g.low <= close <= g.high for g in fvgs)
            bullish_shift = any(e.direction == Trend.BULLISH for e in ms.events[-3:]) if ms.events else False

            score = sum([has_sweep, has_ob, has_fvg, bullish_shift])
            if score >= 3 and (has_ob or has_fvg):
                return ("BUY", close - atr * 2.0, close + atr * 4.0)

        elif htf_trend == Trend.BEARISH:
            has_sweep = any(s.close_back_inside and s.sweep_price > close for s in liq.sweeps)
            has_ob = any(ob.direction == "bearish" and not ob.mitigated and ob.low <= close <= ob.high for ob in obs)
            has_fvg = any(g.direction == "bearish" and not g.filled and g.low <= close <= g.high for g in fvgs)
            bearish_shift = any(e.direction == Trend.BEARISH for e in ms.events[-3:]) if ms.events else False

            score = sum([has_sweep, has_ob, has_fvg, bearish_shift])
            if score >= 3 and (has_ob or has_fvg):
                return ("SELL", close + atr * 2.0, close - atr * 4.0)

        return None

    @staticmethod
    def _check_exit(
        trade: BacktestTrade, high: float, low: float, idx: int
    ) -> BacktestTrade:
        if trade.direction == "BUY":
            if low <= trade.sl:
                trade.exit_price = trade.sl
                trade.exit_idx = idx
                trade.closed = True
            elif high >= trade.tp:
                trade.exit_price = trade.tp
                trade.exit_idx = idx
                trade.closed = True
        else:
            if high >= trade.sl:
                trade.exit_price = trade.sl
                trade.exit_idx = idx
                trade.closed = True
            elif low <= trade.tp:
                trade.exit_price = trade.tp
                trade.exit_idx = idx
                trade.closed = True

        if trade.closed:
            Backtester._finalize_trade(trade)
        return trade

    @staticmethod
    def _finalize_trade(trade: BacktestTrade) -> None:
        if trade.direction == "BUY":
            trade.pnl = (trade.exit_price - trade.entry_price) * trade.volume
        else:
            trade.pnl = (trade.entry_price - trade.exit_price) * trade.volume

    @staticmethod
    def _unrealized(trade: Optional[BacktestTrade], price: float) -> float:
        if trade is None:
            return 0.0
        if trade.direction == "BUY":
            return (price - trade.entry_price) * trade.volume
        return (trade.entry_price - price) * trade.volume
