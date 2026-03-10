from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class VolatilityRegime(Enum):
    LOW = auto()
    NORMAL = auto()
    HIGH = auto()
    EXTREME = auto()


@dataclass
class VolatilityResult:
    atr: float
    regime: VolatilityRegime
    atr_percentile: float
    tradeable: bool


class VolatilityModel:
    """ATR-based volatility regime detection.

    Avoids trading in extremely low volatility environments.
    """

    def __init__(
        self,
        atr_period: int = 14,
        lookback: int = 100,
        low_percentile: float = 15.0,
        high_percentile: float = 85.0,
    ) -> None:
        self._atr_period = atr_period
        self._lookback = lookback
        self._low_pct = low_percentile
        self._high_pct = high_percentile

    def analyze(self, df: pd.DataFrame) -> VolatilityResult:
        atr_series = self._compute_atr_series(df)
        if len(atr_series) == 0:
            return VolatilityResult(
                atr=0.0, regime=VolatilityRegime.LOW, atr_percentile=0.0, tradeable=False
            )

        current_atr = float(atr_series.iloc[-1])
        window = atr_series.iloc[-self._lookback:]
        percentile = float(
            (window < current_atr).sum() / len(window) * 100
        )

        regime = self._classify_regime(percentile)
        tradeable = regime not in (VolatilityRegime.LOW,)

        return VolatilityResult(
            atr=current_atr,
            regime=regime,
            atr_percentile=percentile,
            tradeable=tradeable,
        )

    def _compute_atr_series(self, df: pd.DataFrame) -> pd.Series:
        if len(df) < self._atr_period + 1:
            return pd.Series(dtype=float)
        high = df["high"]
        low = df["low"]
        close = df["close"]
        tr = pd.concat(
            [
                high - low,
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return tr.rolling(self._atr_period).mean().dropna()

    def _classify_regime(self, percentile: float) -> VolatilityRegime:
        if percentile < self._low_pct:
            return VolatilityRegime.LOW
        if percentile > 95:
            return VolatilityRegime.EXTREME
        if percentile > self._high_pct:
            return VolatilityRegime.HIGH
        return VolatilityRegime.NORMAL
