from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FVG:
    direction: str  # "bullish" or "bearish"
    high: float
    low: float
    index: int
    timestamp: object = None
    filled: bool = False


class FairValueGap:
    """Detect Fair Value Gaps (imbalances between three consecutive candles).

    Bullish FVG: candle3.low > candle1.high
    Bearish FVG: candle3.high < candle1.low

    Fix: FVG is only "filled" when price retraces more than *fill_threshold*
    of the gap (default 50%).  A partial touch does NOT invalidate the gap.
    """

    def __init__(self, max_gaps: int = 30, fill_threshold: float = 0.5) -> None:
        self._max_gaps = max_gaps
        self._fill_threshold = fill_threshold

    def detect(self, df: pd.DataFrame) -> List[FVG]:
        highs = df["high"].values
        lows = df["low"].values
        timestamps = df.index

        gaps: List[FVG] = []

        for i in range(2, len(highs)):
            c1_high = highs[i - 2]
            c3_low = lows[i]

            if c3_low > c1_high:
                gaps.append(FVG(
                    direction="bullish",
                    high=float(c3_low),
                    low=float(c1_high),
                    index=i - 1,
                    timestamp=timestamps[i - 1],
                ))

            c1_low = lows[i - 2]
            c3_high = highs[i]

            if c3_high < c1_low:
                gaps.append(FVG(
                    direction="bearish",
                    high=float(c1_low),
                    low=float(c3_high),
                    index=i - 1,
                    timestamp=timestamps[i - 1],
                ))

        self._mark_filled(gaps, highs, lows)
        return [g for g in gaps[-self._max_gaps:] if not g.filled]

    def _mark_filled(
        self, gaps: List[FVG], highs: np.ndarray, lows: np.ndarray,
    ) -> None:
        """Mark FVG as filled only when price retraces > fill_threshold of the gap.

        For a bullish FVG (low=c1_high, high=c3_low):
          filled when a candle's low penetrates deeper than 50% of the gap height.
        For a bearish FVG (low=c3_high, high=c1_low):
          filled when a candle's high penetrates deeper than 50% of the gap height.
        """
        threshold = self._fill_threshold
        for gap in gaps:
            if gap.filled:
                continue
            start = gap.index + 2
            gap_size = gap.high - gap.low
            if gap_size <= 0:
                gap.filled = True
                continue

            if gap.direction == "bullish":
                # Filled when low penetrates below midpoint of gap
                fill_level = gap.high - gap_size * threshold
                for k in range(start, len(lows)):
                    if lows[k] <= fill_level:
                        gap.filled = True
                        break
            else:
                # Filled when high penetrates above midpoint of gap
                fill_level = gap.low + gap_size * threshold
                for k in range(start, len(highs)):
                    if highs[k] >= fill_level:
                        gap.filled = True
                        break
