from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class StructureType(Enum):
    HH = "Higher High"
    HL = "Higher Low"
    LH = "Lower High"
    LL = "Lower Low"


class StructureBreak(Enum):
    BOS = "Break of Structure"
    CHOCH = "Change of Character"


class Trend(Enum):
    BULLISH = auto()
    BEARISH = auto()
    NEUTRAL = auto()


@dataclass
class SwingPoint:
    index: int
    price: float
    is_high: bool
    timestamp: object = None
    confirmed: bool = True


@dataclass
class StructureEvent:
    break_type: StructureBreak
    direction: Trend
    price: float
    index: int


@dataclass
class StructureResult:
    trend: Trend
    swing_highs: List[SwingPoint]
    swing_lows: List[SwingPoint]
    structure_labels: List[StructureType]
    events: List[StructureEvent]


class MarketStructure:
    """Detect swing highs / lows, classify HH/HL/LH/LL, and identify BOS / CHOCH."""

    def __init__(self, swing_lookback: int = 5) -> None:
        self._lookback = swing_lookback

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def analyze(self, df: pd.DataFrame) -> StructureResult:
        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values
        timestamps = df.index

        swing_highs = self._detect_swing_highs(highs, timestamps)
        swing_lows = self._detect_swing_lows(lows, timestamps)

        # Fix #1: labels in chronological order (merged highs + lows)
        labels = self._build_chronological_labels(swing_highs, swing_lows)

        # Fix #2: BOS/CHOCH require candle body-close confirmation
        events = self._detect_structure_breaks(swing_highs, swing_lows, closes)

        trend = self._determine_trend(labels)

        return StructureResult(
            trend=trend,
            swing_highs=swing_highs,
            swing_lows=swing_lows,
            structure_labels=labels,
            events=events,
        )

    # ------------------------------------------------------------------
    # Swing detection  (Fix #3: unconfirmed edge,  Fix #4: no duplicates)
    # ------------------------------------------------------------------

    def _detect_swing_highs(
        self, highs: np.ndarray, timestamps: pd.Index
    ) -> List[SwingPoint]:
        points: List[SwingPoint] = []
        lb = self._lookback
        n = len(highs)

        # Confirmed: full lookback window on both sides
        for i in range(lb, max(lb, n - lb)):
            if self._is_swing_high(highs, i, i - lb, i + lb + 1):
                points.append(
                    SwingPoint(
                        index=i, price=float(highs[i]), is_high=True,
                        timestamp=timestamps[i], confirmed=True,
                    )
                )

        # Unconfirmed: right edge with partial right-side window
        for i in range(max(lb, n - lb), n):
            if self._is_swing_high(highs, i, i - lb, n):
                # Skip if a nearby confirmed point already dominates
                if (points
                        and points[-1].index >= i - lb
                        and points[-1].price >= highs[i]):
                    continue
                points.append(
                    SwingPoint(
                        index=i, price=float(highs[i]), is_high=True,
                        timestamp=timestamps[i], confirmed=False,
                    )
                )

        return points

    def _detect_swing_lows(
        self, lows: np.ndarray, timestamps: pd.Index
    ) -> List[SwingPoint]:
        points: List[SwingPoint] = []
        lb = self._lookback
        n = len(lows)

        for i in range(lb, max(lb, n - lb)):
            if self._is_swing_low(lows, i, i - lb, i + lb + 1):
                points.append(
                    SwingPoint(
                        index=i, price=float(lows[i]), is_high=False,
                        timestamp=timestamps[i], confirmed=True,
                    )
                )

        for i in range(max(lb, n - lb), n):
            if self._is_swing_low(lows, i, i - lb, n):
                if (points
                        and points[-1].index >= i - lb
                        and points[-1].price <= lows[i]):
                    continue
                points.append(
                    SwingPoint(
                        index=i, price=float(lows[i]), is_high=False,
                        timestamp=timestamps[i], confirmed=False,
                    )
                )

        return points

    # ------------------------------------------------------------------
    # Helpers for swing detection
    # ------------------------------------------------------------------

    @staticmethod
    def _is_swing_high(highs: np.ndarray, i: int, left: int, right: int) -> bool:
        """True when highs[i] is the maximum in [left, right).

        Fix #4: if multiple indices share the same max value,
        only the first (leftmost) one qualifies — no duplicates.
        """
        val = highs[i]
        if val < np.max(highs[left:right]):
            return False
        # Reject if any earlier bar in the window is already >= val
        for j in range(left, i):
            if highs[j] >= val:
                return False
        return True

    @staticmethod
    def _is_swing_low(lows: np.ndarray, i: int, left: int, right: int) -> bool:
        val = lows[i]
        if val > np.min(lows[left:right]):
            return False
        for j in range(left, i):
            if lows[j] <= val:
                return False
        return True

    # ------------------------------------------------------------------
    # Fix #1: chronological labels
    # ------------------------------------------------------------------

    @staticmethod
    def _build_chronological_labels(
        swing_highs: List[SwingPoint], swing_lows: List[SwingPoint],
    ) -> List[StructureType]:
        """Merge swing highs and lows by index, then classify sequentially.

        Previous code appended all high-labels first, then all low-labels,
        so ``labels[-4:]`` returned the last few low-comparisons instead of
        the four most recent chronological events.
        """
        all_swings = sorted(swing_highs + swing_lows, key=lambda sp: sp.index)

        labels: List[StructureType] = []
        last_sh: Optional[SwingPoint] = None
        last_sl: Optional[SwingPoint] = None

        for sp in all_swings:
            if sp.is_high:
                if last_sh is not None:
                    labels.append(
                        StructureType.HH if sp.price > last_sh.price
                        else StructureType.LH
                    )
                last_sh = sp
            else:
                if last_sl is not None:
                    labels.append(
                        StructureType.HL if sp.price > last_sl.price
                        else StructureType.LL
                    )
                last_sl = sp

        return labels

    # ------------------------------------------------------------------
    # Fix #2: BOS / CHOCH with body-close confirmation
    # ------------------------------------------------------------------

    def _detect_structure_breaks(
        self,
        swing_highs: List[SwingPoint],
        swing_lows: List[SwingPoint],
        closes: np.ndarray,
    ) -> List[StructureEvent]:
        """Only actual level breaks (HH with close above prev SH, or LL with
        close below prev SL) produce BOS / CHOCH events.

        LH and HL are structural observations — they do not break a level,
        so they do not generate events.
        """
        events: List[StructureEvent] = []
        prev_trend: Optional[Trend] = None

        all_swings = sorted(
            swing_highs + swing_lows, key=lambda sp: sp.index,
        )

        last_sh: Optional[SwingPoint] = None
        last_sl: Optional[SwingPoint] = None

        for sp in all_swings:
            if sp.is_high:
                if (last_sh is not None
                        and sp.price > last_sh.price
                        and self._has_close_beyond(
                            closes, last_sh.index, sp.index,
                            last_sh.price, bullish=True)):
                    # Bullish break confirmed by candle body close
                    new_trend = Trend.BULLISH
                    if prev_trend == Trend.BEARISH:
                        events.append(StructureEvent(
                            break_type=StructureBreak.CHOCH,
                            direction=new_trend,
                            price=sp.price,
                            index=sp.index,
                        ))
                    elif prev_trend is not None:
                        events.append(StructureEvent(
                            break_type=StructureBreak.BOS,
                            direction=new_trend,
                            price=sp.price,
                            index=sp.index,
                        ))
                    prev_trend = new_trend
                last_sh = sp
            else:
                if (last_sl is not None
                        and sp.price < last_sl.price
                        and self._has_close_beyond(
                            closes, last_sl.index, sp.index,
                            last_sl.price, bullish=False)):
                    # Bearish break confirmed by candle body close
                    new_trend = Trend.BEARISH
                    if prev_trend == Trend.BULLISH:
                        events.append(StructureEvent(
                            break_type=StructureBreak.CHOCH,
                            direction=new_trend,
                            price=sp.price,
                            index=sp.index,
                        ))
                    elif prev_trend is not None:
                        events.append(StructureEvent(
                            break_type=StructureBreak.BOS,
                            direction=new_trend,
                            price=sp.price,
                            index=sp.index,
                        ))
                    prev_trend = new_trend
                last_sl = sp

        return events

    @staticmethod
    def _has_close_beyond(
        closes: np.ndarray,
        from_idx: int,
        to_idx: int,
        level: float,
        bullish: bool,
    ) -> bool:
        """True if any candle between *from_idx* and *to_idx* (inclusive)
        closed beyond *level*."""
        segment = closes[from_idx + 1: to_idx + 1]
        if len(segment) == 0:
            return False
        if bullish:
            return bool(np.any(segment > level))
        return bool(np.any(segment < level))

    # ------------------------------------------------------------------
    # Trend from labels (unchanged logic, fixed input order)
    # ------------------------------------------------------------------

    @staticmethod
    def _determine_trend(labels: List[StructureType]) -> Trend:
        if not labels:
            return Trend.NEUTRAL
        recent = labels[-4:]
        bullish = sum(
            1 for label in recent if label in (StructureType.HH, StructureType.HL)
        )
        bearish = sum(
            1 for label in recent if label in (StructureType.LH, StructureType.LL)
        )
        if bullish > bearish:
            return Trend.BULLISH
        if bearish > bullish:
            return Trend.BEARISH
        return Trend.NEUTRAL
