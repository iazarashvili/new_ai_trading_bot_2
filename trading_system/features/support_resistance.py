from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd

from trading_system.features.market_structure import MarketStructure, SwingPoint

logger = logging.getLogger(__name__)


@dataclass
class SRZone:
    level: float
    upper: float
    lower: float
    strength: int  # number of swing touches
    zone_type: str  # "support", "resistance", or "pivot"


class SupportResistance:
    """Cluster swing highs/lows into support and resistance zones."""

    def __init__(self, tolerance_atr_mult: float = 0.5, atr_period: int = 14) -> None:
        self._tol_mult = tolerance_atr_mult
        self._atr_period = atr_period
        self._market_structure = MarketStructure()

    def compute_zones(self, df: pd.DataFrame) -> List[SRZone]:
        atr = self._compute_atr(df)
        if atr == 0:
            return []

        tolerance = atr * self._tol_mult
        ms = self._market_structure.analyze(df)
        levels = [sp.price for sp in ms.swing_highs + ms.swing_lows]

        if not levels:
            return []

        clusters = self._cluster_levels(levels, tolerance)
        close = float(df["close"].iloc[-1])

        zones: List[SRZone] = []
        for center, count in clusters:
            zone_type = "support" if center < close else "resistance"
            zones.append(SRZone(
                level=center,
                upper=center + tolerance,
                lower=center - tolerance,
                strength=count,
                zone_type=zone_type,
            ))

        zones.sort(key=lambda z: z.strength, reverse=True)
        return zones

    def _compute_atr(self, df: pd.DataFrame) -> float:
        if len(df) < self._atr_period + 1:
            return 0.0
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(
                np.abs(high[1:] - close[:-1]),
                np.abs(low[1:] - close[:-1]),
            ),
        )
        return float(np.mean(tr[-self._atr_period:]))

    @staticmethod
    def _cluster_levels(
        levels: List[float], tolerance: float
    ) -> List[tuple[float, int]]:
        if not levels:
            return []
        sorted_levels = sorted(levels)
        clusters: List[tuple[float, int]] = []
        cluster: List[float] = [sorted_levels[0]]

        for lv in sorted_levels[1:]:
            if lv - cluster[-1] <= tolerance:
                cluster.append(lv)
            else:
                clusters.append((float(np.mean(cluster)), len(cluster)))
                cluster = [lv]
        if cluster:
            clusters.append((float(np.mean(cluster)), len(cluster)))

        return clusters
