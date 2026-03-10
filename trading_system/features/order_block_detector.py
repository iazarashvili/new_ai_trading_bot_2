from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class OrderBlock:
    direction: str  # "bullish" or "bearish"
    high: float
    low: float
    index: int
    timestamp: object = None
    mitigated: bool = False


class OrderBlockDetector:
    """Detect order blocks: the last opposite candle before an institutional impulse.

    Impulse rule: candle_range > average_range * impulse_multiplier
    """

    def __init__(
        self,
        impulse_multiplier: float = 1.8,
        avg_period: int = 20,
        max_blocks: int = 20,
    ) -> None:
        self._impulse_mult = impulse_multiplier
        self._avg_period = avg_period
        self._max_blocks = max_blocks

    def detect(self, df: pd.DataFrame) -> List[OrderBlock]:
        opens = df["open"].values
        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values
        timestamps = df.index

        ranges = highs - lows
        avg_range = pd.Series(ranges).rolling(self._avg_period).mean().values

        blocks: List[OrderBlock] = []

        for i in range(self._avg_period + 1, len(closes)):
            candle_range = ranges[i]
            if np.isnan(avg_range[i - 1]) or avg_range[i - 1] == 0:
                continue

            if candle_range <= avg_range[i - 1] * self._impulse_mult:
                continue

            is_bullish_impulse = closes[i] > opens[i]
            is_bearish_impulse = closes[i] < opens[i]

            if is_bullish_impulse:
                # Find last bearish candle before impulse
                for j in range(i - 1, max(i - 10, 0), -1):
                    if closes[j] < opens[j]:
                        blocks.append(OrderBlock(
                            direction="bullish",
                            high=float(highs[j]),
                            low=float(lows[j]),
                            index=j,
                            timestamp=timestamps[j],
                        ))
                        break

            elif is_bearish_impulse:
                for j in range(i - 1, max(i - 10, 0), -1):
                    if closes[j] > opens[j]:
                        blocks.append(OrderBlock(
                            direction="bearish",
                            high=float(highs[j]),
                            low=float(lows[j]),
                            index=j,
                            timestamp=timestamps[j],
                        ))
                        break

        self._mark_mitigated(blocks, highs, lows)
        return blocks[-self._max_blocks:]

    @staticmethod
    def _mark_mitigated(
        blocks: List[OrderBlock], highs: np.ndarray, lows: np.ndarray
    ) -> None:
        for ob in blocks:
            if ob.mitigated:
                continue
            start = ob.index + 1
            if ob.direction == "bullish":
                for k in range(start, len(lows)):
                    if lows[k] < ob.low:
                        ob.mitigated = True
                        break
            else:
                for k in range(start, len(highs)):
                    if highs[k] > ob.high:
                        ob.mitigated = True
                        break
