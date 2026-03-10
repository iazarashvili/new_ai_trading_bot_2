from __future__ import annotations

import logging
import math
from typing import Optional

from trading_system.config.risk_limits import RISK_LIMITS
from trading_system.config.symbols import SymbolSpec, get_symbol_spec

logger = logging.getLogger(__name__)


class PositionSizer:
    """Calculate lot size based on account balance and stop-loss distance.

    lot_size = (balance * risk_pct) / stop_loss_distance
    Clamped to symbol min/max lot and rounded to lot_step.
    """

    def __init__(self, risk_pct: Optional[float] = None) -> None:
        self._risk_pct = (risk_pct or RISK_LIMITS.risk_per_trade_pct) / 100.0

    def calculate(
        self,
        balance: float,
        stop_loss_distance: float,
        symbol: str,
    ) -> float:
        if stop_loss_distance <= 0:
            logger.warning("Invalid SL distance %.5f for %s", stop_loss_distance, symbol)
            return 0.0

        spec = get_symbol_spec(symbol)
        risk_amount = balance * self._risk_pct

        if spec.contract_size > 0:
            raw_lots = risk_amount / (stop_loss_distance * spec.contract_size)
        else:
            raw_lots = risk_amount / stop_loss_distance

        lots = self._round_to_step(raw_lots, spec.lot_step)
        lots = max(spec.min_lot, min(lots, spec.max_lot))

        logger.debug(
            "Position size for %s: balance=%.2f risk=%.2f sl_dist=%.5f -> %.2f lots",
            symbol, balance, risk_amount, stop_loss_distance, lots,
        )
        return lots

    @staticmethod
    def _round_to_step(value: float, step: float) -> float:
        if step <= 0:
            return value
        return math.floor(value / step) * step
