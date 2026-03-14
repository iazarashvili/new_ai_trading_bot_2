from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import pandas as pd

from trading_system.features.market_structure import MarketStructure, StructureResult, Trend

logger = logging.getLogger(__name__)


@dataclass
class MTFBias:
    macro_trend: Trend      # D1
    structure_dir: Trend     # H4
    liquidity_bias: Trend    # H1
    execution_trend: Trend   # M15
    aligned: bool


class MultiTimeframeStrategy:
    """Coordinate multi-timeframe analysis.

    D1 -> macro trend
    H4 -> structure direction
    H1 -> liquidity targets
    M15 -> execution

    Fix: alignment is relaxed — D1 macro trend is primary.
    H4 confirms when available, but NEUTRAL H4 no longer blocks signals.
    Previously D1 == H4 was required, killing all signals in ranging H4.
    """

    TF_ROLES = {
        "D1": "macro_trend",
        "H4": "structure_dir",
        "H1": "liquidity_bias",
        "M5": "execution_trend",
        "M15": "execution_trend",
    }

    def __init__(self) -> None:
        self._market_structure = MarketStructure()

    def compute_bias(
        self,
        candles_by_tf: Dict[str, pd.DataFrame],
        features: Dict[str, Dict[str, Any]],
    ) -> MTFBias:
        trends: Dict[str, Trend] = {}

        for tf, role in self.TF_ROLES.items():
            if tf in features and "market_structure" in features[tf]:
                ms: StructureResult = features[tf]["market_structure"]
                trends[role] = ms.trend
            else:
                trends[role] = Trend.NEUTRAL

        macro = trends.get("macro_trend", Trend.NEUTRAL)
        structure = trends.get("structure_dir", Trend.NEUTRAL)

        if macro == Trend.NEUTRAL:
            # No clear D1 trend — never trade
            aligned = False
        elif structure == Trend.NEUTRAL:
            # D1 has direction, H4 is neutral (ranging) — allow trading
            # with D1 bias alone. Previously this blocked all signals.
            aligned = True
        else:
            # Both have direction — they must agree
            aligned = macro == structure

        return MTFBias(
            macro_trend=macro,
            structure_dir=structure,
            liquidity_bias=trends.get("liquidity_bias", Trend.NEUTRAL),
            execution_trend=trends.get("execution_trend", Trend.NEUTRAL),
            aligned=aligned,
        )
