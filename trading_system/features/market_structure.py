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

    def analyze(self, df: pd.DataFrame) -> StructureResult:
        highs = df["high"].values
        lows = df["low"].values
        timestamps = df.index

        swing_highs = self._detect_swing_highs(highs, timestamps)
        swing_lows = self._detect_swing_lows(lows, timestamps)

        labels: List[StructureType] = []
        events: List[StructureEvent] = []

        for i in range(1, len(swing_highs)):
            prev, curr = swing_highs[i - 1], swing_highs[i]
            labels.append(
                StructureType.HH if curr.price > prev.price else StructureType.LH
            )

        for i in range(1, len(swing_lows)):
            prev, curr = swing_lows[i - 1], swing_lows[i]
            labels.append(
                StructureType.HL if curr.price > prev.price else StructureType.LL
            )

        events = self._detect_structure_breaks(swing_highs, swing_lows, highs, lows)
        trend = self._determine_trend(labels)

        return StructureResult(
            trend=trend,
            swing_highs=swing_highs,
            swing_lows=swing_lows,
            structure_labels=labels,
            events=events,
        )

    def _detect_swing_highs(
        self, highs: np.ndarray, timestamps: pd.Index
    ) -> List[SwingPoint]:
        points: List[SwingPoint] = []
        lb = self._lookback
        for i in range(lb, len(highs) - lb):
            if highs[i] == max(highs[i - lb : i + lb + 1]):
                points.append(
                    SwingPoint(index=i, price=float(highs[i]), is_high=True, timestamp=timestamps[i])
                )
        return points

    def _detect_swing_lows(
        self, lows: np.ndarray, timestamps: pd.Index
    ) -> List[SwingPoint]:
        points: List[SwingPoint] = []
        lb = self._lookback
        for i in range(lb, len(lows) - lb):
            if lows[i] == min(lows[i - lb : i + lb + 1]):
                points.append(
                    SwingPoint(index=i, price=float(lows[i]), is_high=False, timestamp=timestamps[i])
                )
        return points

    def _detect_structure_breaks(
        self,
        swing_highs: List[SwingPoint],
        swing_lows: List[SwingPoint],
        highs: np.ndarray,
        lows: np.ndarray,
    ) -> List[StructureEvent]:
        events: List[StructureEvent] = []
        prev_trend: Optional[Trend] = None

        all_swings = sorted(
            [(sp, True) for sp in swing_highs] + [(sp, False) for sp in swing_lows],
            key=lambda x: x[0].index,
        )

        last_sh: Optional[SwingPoint] = None
        last_sl: Optional[SwingPoint] = None

        for sp, is_high in all_swings:
            if is_high:
                if last_sh is not None:
                    if sp.price > last_sh.price:
                        new_trend = Trend.BULLISH
                    else:
                        new_trend = Trend.BEARISH
                    if prev_trend is not None and new_trend != prev_trend:
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
                if last_sl is not None:
                    if sp.price < last_sl.price:
                        new_trend = Trend.BEARISH
                    else:
                        new_trend = Trend.BULLISH
                    if prev_trend is not None and new_trend != prev_trend:
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
    def _determine_trend(labels: List[StructureType]) -> Trend:
        if not labels:
            return Trend.NEUTRAL
        recent = labels[-4:]
        bullish = sum(1 for l in recent if l in (StructureType.HH, StructureType.HL))
        bearish = sum(1 for l in recent if l in (StructureType.LH, StructureType.LL))
        if bullish > bearish:
            return Trend.BULLISH
        if bearish > bullish:
            return Trend.BEARISH
        return Trend.NEUTRAL
