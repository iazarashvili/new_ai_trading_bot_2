from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class RiskLimits:
    risk_per_trade_pct: float = 1.0
    max_open_trades: int = 1
    max_daily_loss_pct: float = 3.0
    max_weekly_loss_pct: float = 6.0
    max_correlation_exposure: float = 0.8
    min_reward_risk_ratio: float = 2.0
    cooldown_minutes: int = 15
    min_sl_pips: float = 5.0
    min_sl_spread_mult: float = 2.0


# Forex – დაბალი ვოლატილობა BTC-თან შედარებით, მჭიდრო სპრედი
SYMBOL_SL_OVERRIDES: Dict[str, Dict[str, float]] = {
    "EURUSDm": {"min_sl_pips": 10.0, "min_sl_spread_mult": 2.0},
    "GBPUSDm": {"min_sl_pips": 12.0, "min_sl_spread_mult": 2.5},
}

RISK_LIMITS = RiskLimits()
