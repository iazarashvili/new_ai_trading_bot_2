from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class LiquidityType(Enum):
    EQUAL_HIGHS = auto()
    EQUAL_LOWS = auto()
    RANGE_HIGH = auto()
    RANGE_LOW = auto()
    SESSION_HIGH = auto()
    SESSION_LOW = auto()


@dataclass
class LiquidityPool:
    level: float
    pool_type: LiquidityType
    index: int
    swept: bool = False


@dataclass
class LiquiditySweep:
    pool: LiquidityPool
    sweep_index: int
    sweep_price: float
    close_back_inside: bool


@dataclass
class LiquidityResult:
    pools: List[LiquidityPool]
    sweeps: List[LiquiditySweep]


class LiquidityModel:
    """Identify liquidity pools and detect sweeps.

    Fixes applied:
    - Equal highs/lows tolerance uses ATR-based absolute distance (not %)
    - Sweep detection scans last *sweep_window* candles, not only the last one
    """

    def __init__(
        self,
        equal_tolerance_atr_mult: float = 0.3,
        lookback: int = 50,
        sweep_window: int = 5,
    ) -> None:
        self._tol_atr_mult = equal_tolerance_atr_mult
        self._lookback = lookback
        self._sweep_window = sweep_window

    def analyze(self, df: pd.DataFrame) -> LiquidityResult:
        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values

        atr = self._quick_atr(highs, lows, closes)

        pools: List[LiquidityPool] = []
        tolerance = atr * self._tol_atr_mult
        pools.extend(self._find_equal_highs(highs, tolerance))
        pools.extend(self._find_equal_lows(lows, tolerance))
        pools.extend(self._find_range_extremes(highs, lows))

        sweeps = self._detect_sweeps(pools, highs, lows, closes)
        return LiquidityResult(pools=pools, sweeps=sweeps)

    # ------------------------------------------------------------------
    # ATR helper
    # ------------------------------------------------------------------

    @staticmethod
    def _quick_atr(
        highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14,
    ) -> float:
        """Simple ATR for tolerance calculation."""
        if len(highs) < period + 1:
            if len(highs) > 0:
                return float(np.mean(highs - lows))
            return 0.0
        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                np.abs(highs[1:] - closes[:-1]),
                np.abs(lows[1:] - closes[:-1]),
            ),
        )
        return float(np.mean(tr[-period:]))

    # ------------------------------------------------------------------
    # Pool detection — ATR-based tolerance instead of percentage
    # ------------------------------------------------------------------

    def _find_equal_highs(self, highs: np.ndarray, tolerance: float) -> List[LiquidityPool]:
        pools: List[LiquidityPool] = []
        n = len(highs)
        window = min(self._lookback, n)
        recent = highs[-window:]
        used = set()
        for i in range(len(recent)):
            if i in used:
                continue
            for j in range(i + 1, len(recent)):
                if j in used:
                    continue
                if recent[j] == 0:
                    continue
                if abs(recent[i] - recent[j]) < tolerance:
                    level = (recent[i] + recent[j]) / 2.0
                    pools.append(LiquidityPool(
                        level=level,
                        pool_type=LiquidityType.EQUAL_HIGHS,
                        index=n - window + j,
                    ))
                    used.add(i)
                    used.add(j)
                    break
        return pools

    def _find_equal_lows(self, lows: np.ndarray, tolerance: float) -> List[LiquidityPool]:
        pools: List[LiquidityPool] = []
        n = len(lows)
        window = min(self._lookback, n)
        recent = lows[-window:]
        used = set()
        for i in range(len(recent)):
            if i in used:
                continue
            for j in range(i + 1, len(recent)):
                if j in used:
                    continue
                if recent[j] == 0:
                    continue
                if abs(recent[i] - recent[j]) < tolerance:
                    level = (recent[i] + recent[j]) / 2.0
                    pools.append(LiquidityPool(
                        level=level,
                        pool_type=LiquidityType.EQUAL_LOWS,
                        index=n - window + j,
                    ))
                    used.add(i)
                    used.add(j)
                    break
        return pools

    def _find_range_extremes(
        self, highs: np.ndarray, lows: np.ndarray,
    ) -> List[LiquidityPool]:
        window = min(self._lookback, len(highs))
        recent_highs = highs[-window:]
        recent_lows = lows[-window:]
        n = len(highs)
        pools: List[LiquidityPool] = []
        if len(recent_highs) > 0:
            rh_idx = int(np.argmax(recent_highs))
            pools.append(LiquidityPool(
                level=float(recent_highs[rh_idx]),
                pool_type=LiquidityType.RANGE_HIGH,
                index=n - window + rh_idx,
            ))
        if len(recent_lows) > 0:
            rl_idx = int(np.argmin(recent_lows))
            pools.append(LiquidityPool(
                level=float(recent_lows[rl_idx]),
                pool_type=LiquidityType.RANGE_LOW,
                index=n - window + rl_idx,
            ))
        return pools

    # ------------------------------------------------------------------
    # Sweep detection — scan last N candles, not only the last one
    # ------------------------------------------------------------------

    def _detect_sweeps(
        self,
        pools: List[LiquidityPool],
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
    ) -> List[LiquiditySweep]:
        sweeps: List[LiquiditySweep] = []
        n = len(closes)
        if n < 2:
            return sweeps

        scan_start = max(0, n - self._sweep_window)

        for pool in pools:
            if pool.swept:
                continue

            is_high_pool = pool.pool_type in (
                LiquidityType.EQUAL_HIGHS,
                LiquidityType.RANGE_HIGH,
                LiquidityType.SESSION_HIGH,
            )

            for idx in range(scan_start, n):
                if is_high_pool:
                    # Sweep above: wick went above pool level, body closed below
                    if highs[idx] > pool.level and closes[idx] < pool.level:
                        sweeps.append(LiquiditySweep(
                            pool=pool,
                            sweep_index=idx,
                            sweep_price=float(highs[idx]),
                            close_back_inside=True,
                        ))
                        pool.swept = True
                        break
                else:
                    # Sweep below: wick went below pool level, body closed above
                    if lows[idx] < pool.level and closes[idx] > pool.level:
                        sweeps.append(LiquiditySweep(
                            pool=pool,
                            sweep_index=idx,
                            sweep_price=float(lows[idx]),
                            close_back_inside=True,
                        ))
                        pool.swept = True
                        break

        return sweeps
