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
    """Identify liquidity pools (equal highs/lows, range extremes, sessions)
    and detect liquidity sweeps."""

    def __init__(self, equal_tolerance_pct: float = 0.02, lookback: int = 50) -> None:
        self._tol_pct = equal_tolerance_pct
        self._lookback = lookback

    def analyze(self, df: pd.DataFrame) -> LiquidityResult:
        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values

        pools: List[LiquidityPool] = []
        pools.extend(self._find_equal_highs(highs))
        pools.extend(self._find_equal_lows(lows))
        pools.extend(self._find_range_extremes(highs, lows))

        sweeps = self._detect_sweeps(pools, highs, lows, closes)
        return LiquidityResult(pools=pools, sweeps=sweeps)

    def _find_equal_highs(self, highs: np.ndarray) -> List[LiquidityPool]:
        pools: List[LiquidityPool] = []
        n = len(highs)
        window = min(self._lookback, n)
        recent = highs[-window:]
        for i in range(len(recent)):
            for j in range(i + 1, len(recent)):
                if recent[j] == 0:
                    continue
                diff = abs(recent[i] - recent[j]) / recent[j]
                if diff < self._tol_pct:
                    level = (recent[i] + recent[j]) / 2.0
                    pools.append(LiquidityPool(
                        level=level,
                        pool_type=LiquidityType.EQUAL_HIGHS,
                        index=n - window + j,
                    ))
                    break
        return pools

    def _find_equal_lows(self, lows: np.ndarray) -> List[LiquidityPool]:
        pools: List[LiquidityPool] = []
        n = len(lows)
        window = min(self._lookback, n)
        recent = lows[-window:]
        for i in range(len(recent)):
            for j in range(i + 1, len(recent)):
                if recent[j] == 0:
                    continue
                diff = abs(recent[i] - recent[j]) / recent[j]
                if diff < self._tol_pct:
                    level = (recent[i] + recent[j]) / 2.0
                    pools.append(LiquidityPool(
                        level=level,
                        pool_type=LiquidityType.EQUAL_LOWS,
                        index=n - window + j,
                    ))
                    break
        return pools

    def _find_range_extremes(
        self, highs: np.ndarray, lows: np.ndarray
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

    def _detect_sweeps(
        self,
        pools: List[LiquidityPool],
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
    ) -> List[LiquiditySweep]:
        sweeps: List[LiquiditySweep] = []
        if len(closes) < 2:
            return sweeps
        last_idx = len(closes) - 1
        for pool in pools:
            if pool.pool_type in (
                LiquidityType.EQUAL_HIGHS,
                LiquidityType.RANGE_HIGH,
                LiquidityType.SESSION_HIGH,
            ):
                if highs[last_idx] > pool.level and closes[last_idx] < pool.level:
                    sweeps.append(LiquiditySweep(
                        pool=pool,
                        sweep_index=last_idx,
                        sweep_price=float(highs[last_idx]),
                        close_back_inside=True,
                    ))
                    pool.swept = True
            else:
                if lows[last_idx] < pool.level and closes[last_idx] > pool.level:
                    sweeps.append(LiquiditySweep(
                        pool=pool,
                        sweep_index=last_idx,
                        sweep_price=float(lows[last_idx]),
                        close_back_inside=True,
                    ))
                    pool.swept = True
        return sweeps
